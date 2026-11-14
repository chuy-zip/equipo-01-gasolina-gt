"""API del precio de la gasolina en Guatemala.

Sirve la copia de la capa oro y el modelo `champion` que se descargan de Databricks.
La documentación interactiva está en /docs.
"""

from __future__ import annotations

import datetime as dt
import os
from enum import Enum
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

from app import datos

RUTA_ARTEFACTOS = Path(os.getenv("RUTA_ARTEFACTOS", Path(__file__).resolve().parents[1] / "artefactos"))
LIMITE_MAXIMO = 1000


class Combustible(str, Enum):
    super = "super"
    regular = "regular"
    diesel = "diesel"


class Fuente(str, Enum):
    mem = "mem"
    fotos = "fotos"


def crear_app(ruta: Path) -> FastAPI:
    artefactos = datos.cargar(ruta)
    predicciones = datos.predecir(artefactos)

    app = FastAPI(
        title="Precio de la gasolina en Guatemala",
        description=(
            "Precios de referencia del MEM, precios leídos de fotos de gasolineras y la predicción de la "
            "semana siguiente: sube, baja o se mantiene. Datos de la capa oro del pipeline en Databricks. "
            "Equipo 01, MLOps, UVG."
        ),
        version=str(artefactos.manifiesto.get("version_modelo", "")),
    )

    @app.get("/health", summary="Estado del servicio")
    def health():
        manifiesto = artefactos.manifiesto
        return {
            "estado": "ok",
            "modelo": manifiesto.get("modelo"),
            "version_modelo": manifiesto.get("version_modelo"),
            "datos_exportados_en": manifiesto.get("exportado_en"),
            "semana_mas_reciente": manifiesto.get("semana_mas_reciente"),
        }

    @app.get("/precios/actual", summary="Último precio de referencia por combustible")
    def precios_actual(combustible: Combustible | None = None):
        tabla = artefactos.referencia_actual
        if combustible:
            tabla = tabla[tabla["combustible"] == combustible.value]
        return {
            "nota": "Precio igual o menor que precio_referencia es bueno. Hasta limite_normal es normal. Arriba es caro.",
            "datos": datos.registros(tabla),
        }

    @app.get("/precios", summary="Histórico semanal con filtros y paginación")
    def precios(
        combustible: Combustible | None = None,
        desde: dt.date | None = Query(None, description="Primera semana, AAAA-MM-DD"),
        hasta: dt.date | None = Query(None, description="Última semana, AAAA-MM-DD"),
        fuente: Fuente | None = Query(None, description="mem para el precio oficial, fotos para los precios de las fotos"),
        limit: int = Query(100, ge=1, le=LIMITE_MAXIMO),
        offset: int = Query(0, ge=0),
    ):
        if desde and hasta and desde > hasta:
            raise HTTPException(status_code=400, detail="desde no puede ser posterior a hasta")
        tabla = artefactos.precio_semanal
        semana = pd.to_datetime(tabla["semana"]).dt.date
        filtro = pd.Series(True, index=tabla.index)
        if combustible:
            filtro &= tabla["combustible"] == combustible.value
        if fuente:
            filtro &= tabla["fuente"] == fuente.value
        if desde:
            filtro &= semana >= desde
        if hasta:
            filtro &= semana <= hasta
        filtrada = tabla[filtro].sort_values(["semana", "combustible", "fuente"])
        return {
            "total": len(filtrada),
            "limit": limit,
            "offset": offset,
            "datos": datos.registros(filtrada.iloc[offset: offset + limit]),
        }

    @app.get("/prediccion", summary="Predicción de la semana siguiente")
    def prediccion(combustible: Combustible | None = None):
        """El modelo `champion` predice con la semana más reciente de la copia de `gold.features_modelo`.

        `coincide_con_databricks` compara contra lo que guardó el job en `gold.predicciones`.
        Si es true, el modelo empaquetado es el mismo que el de Databricks.
        """
        guardadas = artefactos.predicciones.set_index(["semana", "combustible"])["prediccion"].to_dict()
        tabla = predicciones
        if combustible:
            tabla = tabla[tabla["combustible"] == combustible.value]
        resultado = datos.registros(tabla)
        for fila, original in zip(resultado, tabla.itertuples()):
            esperada = guardadas.get((original.semana_datos, original.combustible))
            fila["coincide_con_databricks"] = None if esperada is None else esperada == original.prediccion
            fila["version_modelo"] = artefactos.manifiesto.get("version_modelo")
        if combustible:
            if not resultado:
                raise HTTPException(status_code=404, detail="No hay predicción para ese combustible")
            return resultado[0]
        return {"datos": resultado}

    @app.get("/modelo/metricas", summary="Exactitud del modelo y de la línea base")
    def modelo_metricas():
        """Métricas de la evaluación temporal: los últimos 2 años que el modelo no vio al entrenar.

        La línea base es la del enunciado: se repite la dirección de la semana anterior.
        """
        tabla = artefactos.metricas_modelo.sort_values("entrenado_en", ascending=False).head(1)
        return datos.registros(tabla)[0]

    return app


app = crear_app(RUTA_ARTEFACTOS)

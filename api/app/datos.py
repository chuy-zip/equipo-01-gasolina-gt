"""Carga los artefactos que descarga `scripts/exportar_para_api.py`: el modelo y la copia de oro.

La API no se conecta a Databricks ni a S3. Todo lo que sirve viene de esta carpeta, que la imagen
de Docker copia al construirse.
"""

from __future__ import annotations

import datetime as dt
import json
import math
from dataclasses import dataclass
from pathlib import Path

import cloudpickle
import pandas as pd

COMBUSTIBLES = ("super", "regular", "diesel")
CLASES = ("sube", "baja", "se_mantiene")


@dataclass
class Artefactos:
    modelo: object
    manifiesto: dict
    referencia_actual: pd.DataFrame
    precio_semanal: pd.DataFrame
    metricas_modelo: pd.DataFrame
    predicciones: pd.DataFrame
    features_modelo: pd.DataFrame


def cargar(ruta: Path) -> Artefactos:
    """Lee el modelo, el manifiesto y las tablas de oro. Falla al arrancar si falta algo."""
    datos = ruta / "datos"
    with open(ruta / "modelo" / "model.pkl", "rb") as archivo:
        modelo = cloudpickle.load(archivo)
    return Artefactos(
        modelo=modelo,
        manifiesto=json.loads((ruta / "manifiesto.json").read_text(encoding="utf-8")),
        referencia_actual=pd.read_parquet(datos / "referencia_actual.parquet"),
        precio_semanal=pd.read_parquet(datos / "precio_semanal.parquet"),
        metricas_modelo=pd.read_parquet(datos / "metricas_modelo.parquet"),
        predicciones=pd.read_parquet(datos / "predicciones.parquet"),
        features_modelo=pd.read_parquet(datos / "features_modelo.parquet"),
    )


def _valor(valor):
    """Convierte un valor de pandas en algo que JSON entiende."""
    if valor is None or valor is pd.NA or valor is pd.NaT:
        return None
    if isinstance(valor, float) and math.isnan(valor):
        return None
    if isinstance(valor, (pd.Timestamp, dt.datetime, dt.date)):
        return valor.isoformat()
    if hasattr(valor, "item"):
        return valor.item()
    return valor


def registros(tabla: pd.DataFrame) -> list[dict]:
    """Filas de una tabla como lista de diccionarios listos para JSON."""
    return [{columna: _valor(v) for columna, v in fila.items()} for fila in tabla.to_dict("records")]


def predecir(artefactos: Artefactos) -> pd.DataFrame:
    """Aplica el modelo a la semana más reciente de `features_modelo`. Una fila por combustible.

    Usa las mismas columnas con que se entrenó el modelo. Así la API no depende del código de Databricks.
    """
    filas = artefactos.features_modelo
    modelo = artefactos.modelo
    probabilidades = modelo.predict_proba(filas[list(modelo.feature_names_in_)])
    clases = list(modelo.classes_)
    resultado = pd.DataFrame({
        "semana_datos": filas["semana"].to_numpy(),
        "semana": (pd.to_datetime(filas["semana"]) + pd.Timedelta(days=7)).dt.date.to_numpy(),
        "combustible": filas["combustible"].astype(str).to_numpy(),
        "prediccion": [clases[i] for i in probabilidades.argmax(axis=1)],
        "probabilidad": probabilidades.max(axis=1).round(4),
    })
    for clase in CLASES:
        resultado[f"prob_{clase}"] = probabilidades[:, clases.index(clase)].round(4) if clase in clases else 0.0
    return resultado

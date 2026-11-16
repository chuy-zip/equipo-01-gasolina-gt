"""Genera la copia de oro de la API desde los archivos de data/, sin Databricks.

Usa el mismo código de `gas_price` que el pipeline, pero entrena el modelo en local y no usa las
fotos. Sirve cuando no hay acceso a Databricks. El manifiesto queda con `origen: local`.
Para la copia oficial usar `scripts/exportar_para_api.py`.

    pip install -e . pyarrow cloudpickle
    python scripts/exportar_local.py
"""

import datetime as dt
import json
from pathlib import Path

import cloudpickle
import pandas as pd

from gas_price import eia, features, mem, modelo

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "api" / "artefactos"
VERSION_MODELO = "local"


def cargar_precios_oficiales() -> pd.DataFrame:
    crudo = mem.extraer_crudo(mem.leer_hoja(RAIZ / "data" / "mem" / "precios_promedio_nacionales_diarios.xlsx"))
    return mem.a_formato_largo(mem.limpiar(crudo))


def cargar_precios_internacionales() -> pd.DataFrame:
    partes = []
    for serie, config in eia.SERIES.items():
        datos = eia.leer(RAIZ / "data" / "eia" / config["archivo"])
        datos.insert(1, "serie", serie)
        partes.append(datos)
    return pd.concat(partes, ignore_index=True)


def main() -> None:
    diarios = features.precios_diarios(cargar_precios_oficiales())
    semanales = features.features_modelo(diarios, cargar_precios_internacionales())
    ahora = pd.Timestamp.now(tz="UTC")

    _, resultado = modelo.evaluar(semanales)
    campeon = modelo.construir_modelo().fit(
        modelo.con_etiqueta(semanales)[modelo.VARIABLES], modelo.con_etiqueta(semanales)["etiqueta"]
    )
    predicciones = modelo.predecir(campeon, modelo.semana_a_predecir(semanales), VERSION_MODELO)
    predicciones["predicho_en"] = ahora

    metricas = modelo.fila_de_metricas(resultado, VERSION_MODELO)
    metricas["entrenado_en"] = ahora

    tablas = {
        "referencia_actual": features.referencia_actual(diarios),
        "precio_semanal": features.precio_semanal(diarios),
        "metricas_modelo": metricas,
        "predicciones": predicciones,
        "features_modelo": semanales[semanales["semana"] == semanales["semana"].max()].sort_values("combustible"),
    }
    carpeta = DESTINO / "datos"
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre, tabla in tablas.items():
        tabla.to_parquet(carpeta / f"{nombre}.parquet", index=False)
        print(f"{nombre}: {len(tabla)} filas")

    carpeta_modelo = DESTINO / "modelo"
    carpeta_modelo.mkdir(parents=True, exist_ok=True)
    with open(carpeta_modelo / "model.pkl", "wb") as archivo:
        cloudpickle.dump(campeon, archivo)

    manifiesto = {
        "origen": "local",
        "modelo": "local",
        "semana_mas_reciente": str(semanales["semana"].max()),
        "exportado_en": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "version_modelo": VERSION_MODELO,
        "filas": {nombre: len(tabla) for nombre, tabla in tablas.items()},
    }
    (DESTINO / "manifiesto.json").write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()

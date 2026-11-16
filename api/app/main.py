import datetime as dt
import math
from enum import Enum
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

from app import store

DEFAULT_LIMIT = 100
MAX_LIMIT = 1000

app = FastAPI(
    title="Precio de la gasolina en Guatemala",
    description="Precios semanales y predicción de la dirección del precio, leídos de la capa Oro.",
    version="1.0.0",
)


class Fuel(str, Enum):
    super = "super"
    regular = "regular"
    diesel = "diesel"


class Source(str, Enum):
    mem = "mem"
    fotos = "fotos"


def to_records(frame: pd.DataFrame) -> list[dict]:
    frame = frame.astype(object).where(frame.notna(), None)
    records = frame.to_dict(orient="records")
    return [{key: clean(value) for key, value in row.items()} for row in records]


def clean(value):
    if isinstance(value, (dt.date, dt.datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def require_rows(frame: pd.DataFrame, detail: str) -> pd.DataFrame:
    if frame.empty:
        raise HTTPException(status_code=404, detail=detail)
    return frame


@app.get("/health")
def health():
    manifest = store.load_manifest()
    tables = {name: len(store.load_table(name)) for name in store.TABLES}
    return {
        "status": "ok",
        "tablas": tables,
        "exportado_en": manifest.get("exportado_en"),
        "version_modelo": manifest.get("version_modelo"),
    }


@app.get("/precios/actual")
def current_prices(combustible: Optional[Fuel] = None):
    frame = store.load_table("referencia_actual")
    if combustible:
        frame = frame[frame["combustible"] == combustible.value]
    return to_records(require_rows(frame, "Sin precio para ese combustible").sort_values("combustible"))


@app.get("/precios")
def weekly_prices(
    combustible: Optional[Fuel] = None,
    fuente: Optional[Source] = None,
    desde: Optional[dt.date] = None,
    hasta: Optional[dt.date] = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    frame = store.load_table("precio_semanal")
    if combustible:
        frame = frame[frame["combustible"] == combustible.value]
    if fuente:
        frame = frame[frame["fuente"] == fuente.value]
    if desde:
        frame = frame[frame["semana"] >= desde]
    if hasta:
        frame = frame[frame["semana"] <= hasta]
    frame = frame.sort_values(["semana", "combustible", "fuente"], ascending=[False, True, True])
    return {
        "total": len(frame),
        "limit": limit,
        "offset": offset,
        "datos": to_records(frame.iloc[offset : offset + limit]),
    }


@app.get("/prediccion")
def prediction(combustible: Optional[Fuel] = None):
    frame = store.load_table("predicciones")
    if combustible:
        frame = frame[frame["combustible"] == combustible.value]
    frame = require_rows(frame, "Sin predicción para ese combustible")
    latest = frame[frame["semana"] == frame["semana"].max()].sort_values("combustible")
    columns = [
        "semana",
        "semana_objetivo",
        "combustible",
        "prediccion",
        "probabilidad",
        "prob_sube",
        "prob_baja",
        "prob_se_mantiene",
        "version_modelo",
        "predicho_en",
    ]
    records = to_records(latest[columns])
    return records[0] if combustible else records


@app.get("/modelo/metricas")
def model_metrics():
    frame = require_rows(store.load_table("metricas_modelo"), "Sin métricas del modelo")
    latest = frame.sort_values("entrenado_en", ascending=False).iloc[[0]]
    row = to_records(latest)[0]
    return {
        "version_modelo": row["version_modelo"],
        "entrenado_en": row["entrenado_en"],
        "inicio_prueba": row["inicio_prueba"],
        "filas_entrenamiento": row["filas_entrenamiento"],
        "filas_prueba": row["filas_prueba"],
        "supera_linea_base": row["supera_linea_base"],
        "modelo": {
            "balanced_accuracy": row["modelo_balanced_accuracy"],
            "f1_macro": row["modelo_f1_macro"],
            "direccion_con_movimiento": row["modelo_direccion_con_movimiento"],
        },
        "linea_base": {
            "balanced_accuracy": row["linea_base_balanced_accuracy"],
            "f1_macro": row["linea_base_f1_macro"],
            "direccion_con_movimiento": row["linea_base_direccion_con_movimiento"],
        },
    }

"""Tests de la API con artefactos de prueba: un modelo entrenado con datos sintéticos y tablas pequeñas.

Si existe `api/artefactos/` con la copia real de Databricks, también revisa que la predicción coincida.
"""

import datetime as dt
import importlib
import json
import sys
from pathlib import Path

import cloudpickle
import numpy as np
import pandas as pd
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from gas_price import features, modelo  # noqa: E402

RAIZ = Path(__file__).parents[1]
sys.path.insert(0, str(RAIZ / "api"))
COMBUSTIBLES = ["diesel", "regular", "super"]


def _features(semanas: int) -> pd.DataFrame:
    generador = np.random.default_rng(0)
    filas = []
    inicio = dt.date(2026, 1, 6)
    for i in range(semanas):
        for combustible in COMBUSTIBLES:
            fila = {v: float(generador.normal()) for v in features.VARIABLES_NUMERICAS}
            fila.update(semana=inicio + dt.timedelta(weeks=i), combustible=combustible,
                        etiqueta=["sube", "baja", "se_mantiene"][generador.integers(3)])
            filas.append(fila)
    return pd.DataFrame(filas)


def _crear_artefactos(ruta: Path) -> pd.DataFrame:
    historia = _features(40)
    campeon = modelo.construir_modelo().fit(historia[features.VARIABLES], historia["etiqueta"])
    (ruta / "modelo").mkdir(parents=True)
    with open(ruta / "modelo" / "model.pkl", "wb") as archivo:
        cloudpickle.dump(campeon, archivo)

    ultima = historia[historia["semana"] == historia["semana"].max()].drop(columns="etiqueta")
    esperadas = modelo.predecir(campeon, ultima, version_modelo="9")

    carpeta = ruta / "datos"
    carpeta.mkdir()
    ultima.to_parquet(carpeta / "features_modelo.parquet", index=False)
    esperadas.to_parquet(carpeta / "predicciones.parquet", index=False)
    pd.DataFrame({
        "combustible": COMBUSTIBLES, "fecha_referencia": [dt.date(2026, 11, 10)] * 3,
        "precio_referencia": [41.01, 29.98, 32.49], "limite_normal": [42.01, 30.98, 33.49],
        "tipo_cambio": [7.64] * 3, "regimen_fiscal": ["exento"] * 3, "proximo_cambio": [dt.date(2026, 11, 16)] * 3,
    }).to_parquet(carpeta / "referencia_actual.parquet", index=False)
    semanas = [dt.date(2026, 10, 6) + dt.timedelta(weeks=i) for i in range(6)]
    pd.DataFrame([
        {"semana": s, "combustible": c, "fuente": f, "precio_promedio": 30.0, "precio_minimo": 29.0,
         "precio_maximo": 31.0, "n_observaciones": 7}
        for s in semanas for c in COMBUSTIBLES for f in ["mem", "fotos"]
    ]).to_parquet(carpeta / "precio_semanal.parquet", index=False)
    pd.DataFrame([
        {"version_modelo": "8", "entrenado_en": pd.Timestamp("2026-11-01", tz="UTC"), "modelo_balanced_accuracy": 0.5,
         "linea_base_balanced_accuracy": 0.46, "supera_linea_base": True},
        {"version_modelo": "9", "entrenado_en": pd.Timestamp("2026-11-14", tz="UTC"), "modelo_balanced_accuracy": 0.55,
         "linea_base_balanced_accuracy": 0.46, "supera_linea_base": True},
    ]).to_parquet(carpeta / "metricas_modelo.parquet", index=False)
    (ruta / "manifiesto.json").write_text(json.dumps({
        "modelo": "equipo_01.gold.modelo_tendencia_precio", "version_modelo": "9",
        "exportado_en": "2026-11-14T00:00:00+00:00", "semana_mas_reciente": str(historia["semana"].max()),
    }))
    return esperadas


def _cliente(ruta: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("RUTA_ARTEFACTOS", str(ruta))
    import app.main

    return TestClient(importlib.reload(app.main).app)


@pytest.fixture
def cliente_y_esperadas(tmp_path, monkeypatch):
    esperadas = _crear_artefactos(tmp_path)
    return _cliente(tmp_path, monkeypatch), esperadas


def test_health(cliente_y_esperadas):
    cliente, _ = cliente_y_esperadas
    respuesta = cliente.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "ok"
    assert respuesta.json()["version_modelo"] == "9"


def test_precio_actual(cliente_y_esperadas):
    cliente, _ = cliente_y_esperadas
    todos = cliente.get("/precios/actual").json()["datos"]
    assert {fila["combustible"] for fila in todos} == set(COMBUSTIBLES)
    solo = cliente.get("/precios/actual", params={"combustible": "diesel"}).json()["datos"]
    assert solo == [fila for fila in todos if fila["combustible"] == "diesel"]
    assert solo[0]["fecha_referencia"] == "2026-11-10"


def test_precios_filtra_y_pagina(cliente_y_esperadas):
    cliente, _ = cliente_y_esperadas
    respuesta = cliente.get("/precios", params={
        "combustible": "diesel", "desde": "2026-10-13", "hasta": "2026-10-27", "fuente": "mem", "limit": 2})
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 3
    assert len(cuerpo["datos"]) == 2
    assert all(f["combustible"] == "diesel" and f["fuente"] == "mem" for f in cuerpo["datos"])
    siguiente = cliente.get("/precios", params={
        "combustible": "diesel", "desde": "2026-10-13", "hasta": "2026-10-27", "fuente": "mem", "limit": 2, "offset": 2})
    assert [f["semana"] for f in siguiente.json()["datos"]] == ["2026-10-27"]


@pytest.mark.parametrize("params, codigo", [
    ({"combustible": "v_power"}, 422),
    ({"desde": "no-es-fecha"}, 422),
    ({"limit": 0}, 422),
    ({"limit": 5000}, 422),
    ({"desde": "2026-11-01", "hasta": "2026-10-01"}, 400),
])
def test_precios_valida_parametros(cliente_y_esperadas, params, codigo):
    cliente, _ = cliente_y_esperadas
    assert cliente.get("/precios", params=params).status_code == codigo


def test_prediccion_coincide_con_lo_guardado(cliente_y_esperadas):
    cliente, esperadas = cliente_y_esperadas
    for combustible in COMBUSTIBLES:
        cuerpo = cliente.get("/prediccion", params={"combustible": combustible}).json()
        fila = esperadas[esperadas["combustible"] == combustible].iloc[0]
        assert cuerpo["prediccion"] == fila["prediccion"]
        assert cuerpo["probabilidad"] == pytest.approx(fila["probabilidad"], abs=1e-4)
        assert cuerpo["semana"] == fila["semana_objetivo"].isoformat()
        assert cuerpo["coincide_con_databricks"] is True
    assert len(cliente.get("/prediccion").json()["datos"]) == 3


def test_metricas_devuelve_la_version_mas_reciente(cliente_y_esperadas):
    cliente, _ = cliente_y_esperadas
    cuerpo = cliente.get("/modelo/metricas").json()
    assert cuerpo["version_modelo"] == "9"
    assert cuerpo["modelo_balanced_accuracy"] > cuerpo["linea_base_balanced_accuracy"]


def test_documentacion(cliente_y_esperadas):
    cliente, _ = cliente_y_esperadas
    assert cliente.get("/docs").status_code == 200


@pytest.mark.skipif(not (RAIZ / "api" / "artefactos" / "manifiesto.json").exists(),
                    reason="Sin la copia real de Databricks en api/artefactos")
def test_artefactos_reales_coinciden_con_databricks(monkeypatch):
    cliente = _cliente(RAIZ / "api" / "artefactos", monkeypatch)
    for fila in cliente.get("/prediccion").json()["datos"]:
        assert fila["coincide_con_databricks"] is True

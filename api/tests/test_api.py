import pytest
from fastapi.testclient import TestClient

from app.main import app

FUELS = ["super", "regular", "diesel"]
client = TestClient(app)


def test_health():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["tablas"]["predicciones"] > 0


def test_current_prices_returns_every_fuel():
    body = client.get("/precios/actual").json()
    assert sorted(row["combustible"] for row in body) == sorted(FUELS)


@pytest.mark.parametrize("fuel", FUELS)
def test_prediction_per_fuel(fuel):
    body = client.get("/prediccion", params={"combustible": fuel}).json()
    assert body["combustible"] == fuel
    assert body["prediccion"] in {"sube", "baja", "se_mantiene"}
    assert 0 <= body["probabilidad"] <= 1


def test_prices_filters_and_limit():
    body = client.get(
        "/precios", params={"combustible": "diesel", "fuente": "mem", "desde": "2026-01-01", "limit": 5}
    ).json()
    assert len(body["datos"]) <= 5
    assert all(row["combustible"] == "diesel" and row["semana"] >= "2026-01-01" for row in body["datos"])


def test_invalid_fuel_is_rejected():
    assert client.get("/prediccion", params={"combustible": "kerosene"}).status_code == 422


def test_model_metrics_compares_with_baseline():
    body = client.get("/modelo/metricas").json()
    assert "balanced_accuracy" in body["modelo"]
    assert "balanced_accuracy" in body["linea_base"]

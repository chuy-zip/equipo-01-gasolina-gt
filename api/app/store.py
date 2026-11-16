import json
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

DEFAULT_ARTIFACTS_DIR = "artefactos"
TABLES = ("referencia_actual", "precio_semanal", "metricas_modelo", "predicciones")


def artifacts_dir() -> Path:
    return Path(os.environ.get("ARTIFACTS_DIR", DEFAULT_ARTIFACTS_DIR))


@lru_cache(maxsize=None)
def load_table(name: str) -> pd.DataFrame:
    return pd.read_parquet(artifacts_dir() / "datos" / f"{name}.parquet")


@lru_cache(maxsize=1)
def load_manifest() -> dict:
    path = artifacts_dir() / "manifiesto.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def reload() -> None:
    load_table.cache_clear()
    load_manifest.cache_clear()

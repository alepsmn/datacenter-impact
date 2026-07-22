"""Configuración centralizada de los scripts de extracción y carga.

Lee de entorno (`.env`) con valores por defecto sensatos y expone un único
punto de verdad para `PROJECT_ID`, `BUCKET`, `DATASET`, rutas y credenciales.
Importado por `extract_eia`, `extract_epri`, `upload_gcs` y `load_bigquery`
para eliminar la duplicación de constantes entre scripts.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Credenciales / GCP ---
EIA_API_KEY: str | None = os.getenv("EIA_API_KEY")
PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "totemic-life-499613-f2")
KEY_FILE: str = os.getenv("GCP_KEYFILE", "keyfile.json")

# --- Destinos ---
BUCKET: str = os.getenv("GCS_BUCKET", "datacenter-impact-raw")
DATASET: str = os.getenv("BQ_DATASET", "datacenter_impact")
BQ_LOCATION: str = os.getenv("BQ_LOCATION", "US")

# --- Rutas locales (landing crudo) ---
DATA_DIR: Path = Path(os.getenv("DATA_DIR", "data/raw"))
EIA_DIR: Path = DATA_DIR / "eia"
EPRI_DIR: Path = DATA_DIR / "epri"

# --- EIA API ---
EIA_BASE_URL: str = "https://api.eia.gov/v2/electricity/retail-sales/data/"

# Ventana temporal de la extracción (formato YYYY-MM que espera la API).
# Parametrizada por entorno para que la orqueta de Airflow pueda pedir otra
# ventana sin tocar el código: el DAG las inyecta como env vars desde sus
# `params`. Los valores por defecto son el rango completo del análisis.
EIA_START: str = os.getenv("EIA_START", "2015-01")
EIA_END: str = os.getenv("EIA_END", "2024-12")


def configure_logging(level: int = logging.INFO) -> None:
    """Configura el logging raíz con timestamps y nivel.

    Idempotente entre scripts: cada `main()` la invoca una vez al arrancar en
    lugar de usar `print()`. `force=True` reemplaza handlers previos (útil bajo
    Airflow, que ya configura su propio root logger).
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

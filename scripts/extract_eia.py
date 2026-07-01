import json
import logging
import time
import requests
from datetime import datetime
from typing import Any, TypedDict

import config

logger = logging.getLogger(__name__)

# --- Política de red ---
REQUEST_TIMEOUT = 30  # segundos antes de abortar una request colgada
MAX_RETRIES = 4  # intentos totales ante errores transitorios
BACKOFF_BASE = 2  # espera = BACKOFF_BASE ** intento (1s, 2s, 4s, ...)
# Códigos que reintentamos: rate limit y errores de servidor. Un 4xx como 403
# (API key inválida) es determinista → falla rápido, no tiene sentido reintentar.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class EIARecord(TypedDict):
    """Contrato del registro crudo de la API EIA retail-sales.

    Documenta el esquema esperado de cada fila bajo `response.data[]` y debe
    mantenerse alineado con el `schema` de `load_bigquery.py`.
    """

    period: str
    stateid: str
    stateDescription: str
    sectorid: str
    sectorName: str
    sales: float | None
    revenue: float | None
    price: float | None
    customers: float | None

API_KEY = config.EIA_API_KEY
BASE_URL = config.EIA_BASE_URL
OUTPUT_DIR = config.EIA_DIR


def fetch_eia(offset: int = 0, length: int = 5000) -> dict[str, Any]:
    params = {
        "api_key": API_KEY,
        "frequency": "monthly",
        "data[]": ["price", "sales", "revenue", "customers"],
        "facets[sectorid][]": ["RES", "COM", "IND"],
        "start": "2015-01",
        "end": "2024-12",
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "offset": offset,
        "length": length,
    }
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status not in RETRYABLE_STATUS:
                # 4xx determinista (p. ej. 403 key inválida): no reintentar.
                logger.error("EIA respondió %s (no recuperable): %s", status, exc)
                raise
            last_exc = exc
            logger.warning("EIA %s en offset %s (intento %s/%s)",
                           status, offset, attempt + 1, MAX_RETRIES)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            logger.warning("Fallo de red en offset %s (intento %s/%s): %s",
                           offset, attempt + 1, MAX_RETRIES, exc)

        if attempt < MAX_RETRIES - 1:
            wait = BACKOFF_BASE ** attempt
            logger.info("Reintentando en %ss...", wait)
            time.sleep(wait)

    raise RuntimeError(
        f"EIA no respondió tras {MAX_RETRIES} intentos (offset {offset})"
    ) from last_exc

def fetch_all_pages(length: int = 5000) -> list[EIARecord]:
    """Recorre todas las páginas de la API y devuelve TODOS los registros.

    Aísla la lógica de paginación (avanzar `offset`, cortar al alcanzar el
    `total` que reporta la API) de la escritura a disco. Al no tocar red ni
    fichero directamente —solo llama a `fetch_eia`— es testeable mockeando esa
    llamada (ver tests/test_extract_eia.py).
    """
    all_data: list[EIARecord] = []
    offset = 0

    while True:
        logger.info("Fetching offset %s...", offset)
        response = fetch_eia(offset=offset, length=length)
        batch = response["response"]["data"]
        all_data.extend(batch)

        total = response["response"]["total"]
        offset += length
        if offset >= int(total):
            break

    return all_data


def main() -> None:
    config.configure_logging()
    if not API_KEY:
        raise RuntimeError(
            "Falta EIA_API_KEY en el entorno (.env). Revisa .env.example."
        )
    all_data = fetch_all_pages()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"eia_electricity_{datetime.today().strftime('%Y%m%d')}.json"
    with open(output_path, "w") as f:
        for record in all_data:
            f.write(json.dumps(record) + "\n")

    logger.info("Done. %s registros → %s", len(all_data), output_path)

if __name__ == "__main__":
    main()

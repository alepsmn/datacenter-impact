import logging
from pathlib import Path

from google.api_core import exceptions as gcp_exceptions
from google.cloud import bigquery

import config

logger = logging.getLogger(__name__)

KEY_FILE = config.KEY_FILE
PROJECT_ID = config.PROJECT_ID
DATASET = config.DATASET
BUCKET = config.BUCKET

# Esquema espejo del contrato EIARecord en extract_eia.py: mantener alineados.
EIA_SCHEMA = [
    bigquery.SchemaField("period", "STRING"),
    bigquery.SchemaField("stateid", "STRING"),
    bigquery.SchemaField("stateDescription", "STRING"),
    bigquery.SchemaField("sectorid", "STRING"),
    bigquery.SchemaField("sectorName", "STRING"),
    bigquery.SchemaField("sales", "FLOAT64"),
    bigquery.SchemaField("revenue", "FLOAT64"),
    bigquery.SchemaField("price", "FLOAT64"),
    bigquery.SchemaField("customers", "FLOAT64"),
]

EPRI_SCHEMA = [
    bigquery.SchemaField("state", "STRING"),
    bigquery.SchemaField("stateid", "STRING"),
    bigquery.SchemaField("year", "INT64"),
    bigquery.SchemaField("scenario", "STRING"),
    bigquery.SchemaField("annual_energy_gwh", "FLOAT64"),
    bigquery.SchemaField("pct_state_consumed", "FLOAT64"),
]


def load_table(
    client: bigquery.Client,
    gcs_uri: str,
    table_ref: str,
    schema: list[bigquery.SchemaField],
) -> None:
    """Carga NDJSON desde GCS a una tabla de BigQuery.

    WRITE_TRUNCATE hace la carga idempotente: reejecutar deja la tabla en el
    mismo estado en vez de duplicar filas.
    """
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        ignore_unknown_values=True,
    )
    try:
        load_job = client.load_table_from_uri(gcs_uri, table_ref, job_config=job_config)
        load_job.result()  # bloquea hasta terminar; relanza si el job falla
    except gcp_exceptions.GoogleAPIError:
        logger.exception("Fallo cargando %s → %s", gcs_uri, table_ref)
        raise

    table = client.get_table(table_ref)
    logger.info("Cargadas %s filas → %s", table.num_rows, table_ref)


def main() -> None:
    config.configure_logging()
    if not Path(KEY_FILE).exists():
        raise FileNotFoundError(
            f"No se encuentra la credencial '{KEY_FILE}'. "
            "Configúrala con GCP_KEYFILE o coloca keyfile.json en la raíz."
        )
    client = bigquery.Client.from_service_account_json(KEY_FILE)

    dataset_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET}")
    dataset_ref.location = config.BQ_LOCATION
    client.create_dataset(dataset_ref, exists_ok=True)
    logger.info("Dataset %s listo.", DATASET)

    load_table(
        client,
        f"gs://{BUCKET}/eia/*.json",
        f"{PROJECT_ID}.{DATASET}.eia_electricity",
        EIA_SCHEMA,
    )
    load_table(
        client,
        f"gs://{BUCKET}/epri/epri_datacenter_load.ndjson",
        f"{PROJECT_ID}.{DATASET}.epri_datacenter_load",
        EPRI_SCHEMA,
    )


if __name__ == "__main__":
    main()

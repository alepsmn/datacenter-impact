from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()

KEY_FILE = "keyfile.json"
PROJECT_ID = "totemic-life-499613-f2"
DATASET = "datacenter_impact"
TABLE = "eia_electricity"
BUCKET = "datacenter-impact-raw"
GCS_URI = f"gs://{BUCKET}/eia/*.json"

def main():
    client = bigquery.Client.from_service_account_json(KEY_FILE)

    dataset_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET}")
    dataset_ref.location = "US"
    client.create_dataset(dataset_ref, exists_ok=True)
    print(f"Dataset {DATASET} listo.")

    schema = [
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

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        ignore_unknown_values=True,
    )

    table_ref = f"{PROJECT_ID}.{DATASET}.{TABLE}"
    load_job = client.load_table_from_uri(GCS_URI, table_ref, job_config=job_config)
    load_job.result()

    table = client.get_table(table_ref)
    print(f"Cargadas {table.num_rows} filas → {table_ref}")

    # EPRI
    epri_schema = [
        bigquery.SchemaField("state", "STRING"),
        bigquery.SchemaField("stateid", "STRING"),
        bigquery.SchemaField("year", "INT64"),
        bigquery.SchemaField("scenario", "STRING"),
        bigquery.SchemaField("annual_energy_gwh", "FLOAT64"),
        bigquery.SchemaField("pct_state_consumed", "FLOAT64"),
    ]

    epri_job_config = bigquery.LoadJobConfig(
        schema=epri_schema,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        ignore_unknown_values=True,
    )

    epri_table_ref = f"{PROJECT_ID}.{DATASET}.epri_datacenter_load"
    epri_job = client.load_table_from_uri(
        f"gs://{BUCKET}/epri/epri_datacenter_load.ndjson",
        epri_table_ref,
        job_config=epri_job_config
    )
    epri_job.result()

    epri_table = client.get_table(epri_table_ref)
    print(f"Cargadas {epri_table.num_rows} filas → {epri_table_ref}")

if __name__ == "__main__":
    main()
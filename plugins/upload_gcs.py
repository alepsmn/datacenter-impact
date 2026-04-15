import os
from google.cloud import storage

BUCKET_NAME = "iniciocloud-comodios-2026-03-28"

def upload_to_gcs(local_path: str, gcs_path: str) -> str:
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path)
    uri = f"gs://{BUCKET_NAME}/{gcs_path}"
    print(f"Subido: {local_path} → {uri}")
    return uri

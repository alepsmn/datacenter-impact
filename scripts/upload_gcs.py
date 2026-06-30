import glob
import logging
import os
from pathlib import Path

from google.api_core import exceptions as gcp_exceptions
from google.cloud import storage

import config

logger = logging.getLogger(__name__)

BUCKET_NAME = config.BUCKET
KEY_FILE = config.KEY_FILE

def upload_to_gcs(client: storage.Client, local_path: str, destination_blob: str) -> None:
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(destination_blob)
    try:
        blob.upload_from_filename(local_path)
    except gcp_exceptions.GoogleAPIError:
        logger.exception("Fallo subiendo %s a gs://%s/%s",
                         local_path, BUCKET_NAME, destination_blob)
        raise
    logger.info("Subido: %s → gs://%s/%s", local_path, BUCKET_NAME, destination_blob)

def main() -> None:
    config.configure_logging()
    if not Path(KEY_FILE).exists():
        raise FileNotFoundError(
            f"No se encuentra la credencial '{KEY_FILE}'. "
            "Configúrala con GCP_KEYFILE o coloca keyfile.json en la raíz."
        )
    client = storage.Client.from_service_account_json(KEY_FILE)

    # EIA
    files = glob.glob(str(config.EIA_DIR / "*.json"))
    if not files:
        logger.warning("No hay archivos en %s/", config.EIA_DIR)
    for f in files:
        filename = os.path.basename(f)
        upload_to_gcs(client, f, f"eia/{filename}")

    # EPRI
    epri_file = config.EPRI_DIR / "epri_datacenter_load.ndjson"
    if epri_file.exists():
        upload_to_gcs(client, str(epri_file), "epri/epri_datacenter_load.ndjson")
    else:
        logger.warning("No encontrado: %s", epri_file)

if __name__ == "__main__":
    main()

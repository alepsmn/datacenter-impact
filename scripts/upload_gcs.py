import os
import glob
from google.cloud import storage
from dotenv import load_dotenv

load_dotenv()

BUCKET_NAME = "datacenter-impact-raw"
KEY_FILE = "keyfile.json"

def upload_to_gcs(local_path, destination_blob):
    client = storage.Client.from_service_account_json(KEY_FILE)
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(destination_blob)
    blob.upload_from_filename(local_path)
    print(f"Subido: {local_path} → gs://{BUCKET_NAME}/{destination_blob}")

def main():
    files = glob.glob("data/raw/eia/*.json")
    if not files:
        print("No hay archivos en data/raw/eia/")
        return
    for f in files:
        filename = os.path.basename(f)
        upload_to_gcs(f, f"eia/{filename}")

if __name__ == "__main__":
    main()
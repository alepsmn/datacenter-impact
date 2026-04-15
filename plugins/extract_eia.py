import os
import json
import requests
from datetime import datetime

EIA_API_KEY = os.environ["EIA_API_KEY"]
BASE_URL = "https://api.eia.gov/v2/electricity/retail-sales/data/"
STATES = ["VA", "MD", "NC", "TN", "TX"]
OUTPUT_DIR = "/opt/airflow/data/raw/eia"

def extract_state(state: str) -> list:
    params = {
        "api_key": EIA_API_KEY,
        "frequency": "monthly",
        "data[0]": "sales",
        "data[1]": "revenue",
        "data[2]": "price",
        "data[3]": "customers",
        "facets[stateid][]": state,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 500,
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()
    return data["response"]["data"]


def save_raw(state: str, records: list) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{OUTPUT_DIR}/{state}_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump(records, f, indent=2)
    return filename


def extract_and_save(state: str) -> str:
    records = extract_state(state)
    path = save_raw(state, records)
    print(f"{state}: {len(records)} registros → {path}")
    return path

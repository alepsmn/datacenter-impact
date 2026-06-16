import requests
import json
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

API_KEY = os.getenv("EIA_API_KEY")
BASE_URL = "https://api.eia.gov/v2/electricity/retail-sales/data/"
OUTPUT_DIR = "data/raw/eia"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_eia(offset=0, length=5000):
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
    r = requests.get(BASE_URL, params=params)
    r.raise_for_status()
    return r.json()

def main():
    all_data = []
    offset = 0
    length = 5000

    while True:
        print(f"Fetching offset {offset}...")
        response = fetch_eia(offset=offset, length=length)
        batch = response["response"]["data"]
        all_data.extend(batch)

        total = response["response"]["total"]
        offset += length
        if offset >= int(total):
            break

    output_path = f"{OUTPUT_DIR}/eia_electricity_{datetime.today().strftime('%Y%m%d')}.json"
    with open(output_path, "w") as f:
        json.dump(all_data, f)

    print(f"Done. {len(all_data)} registros → {output_path}")

if __name__ == "__main__":
    main()
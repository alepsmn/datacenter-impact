import json
import openpyxl
from pathlib import Path

STATE_TO_ID = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY"
}

SCENARIOS = [
    (1, 2, 2023, "baseline"),
    (3, 4, 2030, "low"),
    (5, 6, 2030, "moderate"),
    (7, 8, 2030, "high"),
    (9, 10, 2030, "higher"),
]

def extract():
    src = Path("data/raw/epri/EPRI_2024_Projections.xlsx")
    out = Path("data/raw/epri/epri_datacenter_load.ndjson")

    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    ws = wb.active

    records = []
    for row in ws.iter_rows(min_row=3, values_only=True):
        state = row[0]
        if not state or state not in STATE_TO_ID:
            continue
        stateid = STATE_TO_ID[state]
        for load_col, pct_col, year, scenario in SCENARIOS:
            load_mwh = row[load_col]
            pct = row[pct_col]
            if load_mwh is None:
                continue
            records.append({
                "state": state,
                "stateid": stateid,
                "year": year,
                "scenario": scenario,
                "annual_energy_gwh": round(load_mwh / 1000, 4),
                "pct_state_consumed": pct,
            })

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    print(f"Extraídos {len(records)} registros → {out}")

if __name__ == "__main__":
    extract()
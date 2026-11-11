"""Project-wide paths and source registry shared by every stage notebook."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# OneDrive source: TeslimDataLakes/<ONEDRIVE_FOLDER>/ (read via onedrive_loader)
ONEDRIVE_FOLDER = "financial_transactions_dataset_analytics_kaggle"
KAGGLE_URL = "https://www.kaggle.com/datasets/computingvictor/transactions-fraud-datasets"

# Local medallion cache (gitignored). Raw data is pulled from OneDrive once, in stage 2.
# P22_DATA_DIR / P22_OUTPUT_DIR let tests run the notebooks against a scratch copy
DATA_DIR = Path(os.environ.get("P22_DATA_DIR", ROOT / "data"))
BRONZE_DIR = DATA_DIR / "bronze"   # as delivered, every column kept as text
SILVER_DIR = DATA_DIR / "silver"   # typed, cleaned, conformed column names
GOLD_DIR = DATA_DIR / "gold"       # analytical models and model outputs
EXPORT_DIR = Path(os.environ.get("P22_OUTPUT_DIR", ROOT / "outputs")) / "powerbi"  # stage 5 reporting extracts (CSV)
SQL_DIR = ROOT / "sql"

# table name -> (source filename, pandas reader kwargs passed through onedrive_loader.load)
SOURCES: dict[str, tuple[str, dict]] = {
    "users": ("users_data.csv", {}),
    "cards": ("cards_data.csv", {}),
    "mcc_codes": ("mcc_codes.json", {"orient": "index"}),
    "fraud_labels": ("train_fraud_labels.json", {}),
    "transactions": ("transactions_data.csv", {}),
}

# Row counts published on the Kaggle dataset page; stage 2 reconciles against these.
EXPECTED_ROWS = {
    "users": 2_000,
    "cards": 6_146,
    "mcc_codes": 109,
    "fraud_labels": 8_914_963,
    "transactions": 13_305_915,
}

RANDOM_STATE = 42


def ensure_dirs() -> None:
    for d in (BRONZE_DIR, SILVER_DIR, GOLD_DIR, EXPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)

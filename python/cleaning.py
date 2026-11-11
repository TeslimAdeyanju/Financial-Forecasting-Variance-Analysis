"""Stage 3: bronze (text) -> silver (typed, conformed names).

Rules applied here are documented in notebook/03-data-cleaning-and-transformation.
Each function takes a bronze DataFrame and returns a new silver DataFrame; it
never mutates its input.
"""
from __future__ import annotations

import pandas as pd

import config


def parse_currency(s: pd.Series) -> pd.Series:
    """'$1,234.50' / '$-77.00' / '($77.00)' -> float. Unparseable values become NaN."""
    text = s.astype("string").str.strip()
    negative_paren = text.str.startswith("(") & text.str.endswith(")")
    cleaned = text.str.replace(r"[$,()\s]", "", regex=True)
    value = pd.to_numeric(cleaned, errors="coerce")
    return value.where(~negative_paren, -value.abs()).astype("float64")


def _yes_no(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().str.upper().map({"YES": True, "NO": False}).astype("boolean")


def _int(s: pd.Series, dtype: str = "Int64") -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype(dtype)


def clean_users(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "user_id": _int(df["id"], "int64"),
            "current_age": _int(df["current_age"]),
            "retirement_age": _int(df["retirement_age"]),
            "birth_year": _int(df["birth_year"]),
            "birth_month": _int(df["birth_month"]),
            "gender": df["gender"].astype("string"),
            "address": df["address"].astype("string"),
            "latitude": pd.to_numeric(df["latitude"], errors="coerce"),
            "longitude": pd.to_numeric(df["longitude"], errors="coerce"),
            "per_capita_income": parse_currency(df["per_capita_income"]),
            "yearly_income": parse_currency(df["yearly_income"]),
            "total_debt": parse_currency(df["total_debt"]),
            "credit_score": _int(df["credit_score"]),
            "num_credit_cards": _int(df["num_credit_cards"]),
        }
    )
    return out


def clean_cards(df: pd.DataFrame) -> pd.DataFrame:
    # card_number and cvv are dropped: no analytical use, and card-like data shouldn't propagate.
    out = pd.DataFrame(
        {
            "card_id": _int(df["id"], "int64"),
            "user_id": _int(df["client_id"], "int64"),
            "card_brand": df["card_brand"].astype("string"),
            "card_type": df["card_type"].astype("string"),
            # both date columns are month/year only, e.g. '12/2022'
            "expires": pd.to_datetime(df["expires"], format="%m/%Y", errors="coerce"),
            "acct_open_date": pd.to_datetime(df["acct_open_date"], format="%m/%Y", errors="coerce"),
            "has_chip": _yes_no(df["has_chip"]),
            "num_cards_issued": _int(df["num_cards_issued"]),
            "credit_limit": parse_currency(df["credit_limit"]),
            "year_pin_last_changed": _int(df["year_pin_last_changed"]),
            "card_on_dark_web": _yes_no(df["card_on_dark_web"]),
        }
    )
    return out


def clean_mcc_codes(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "mcc_code": _int(df["mcc"], "int64"),
            "category_description": df["description"].astype("string").str.strip(),
        }
    )


def clean_fraud_labels(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "transaction_id": _int(df["transaction_id"], "int64"),
            "is_fraud": _yes_no(df["target"]),
        }
    )


def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    amount = parse_currency(df["amount"])
    city = df["merchant_city"].astype("string").str.strip()
    errors = df["errors"].astype("string").str.strip().replace("", pd.NA)
    zip_code = df["zip"].astype("string").str.replace(r"\.0$", "", regex=True)
    out = pd.DataFrame(
        {
            "transaction_id": _int(df["id"], "int64"),
            "transaction_date": pd.to_datetime(df["date"], errors="coerce"),
            "user_id": _int(df["client_id"], "int64"),
            "card_id": _int(df["card_id"], "int64"),
            "amount": amount,
            "is_refund": amount < 0,
            "use_chip": df["use_chip"].astype("category"),
            "merchant_id": _int(df["merchant_id"], "int64"),
            "merchant_city": city,
            # online transactions carry no state/zip; keep them null rather than inventing 'unknown'
            "merchant_state": df["merchant_state"].astype("string").str.strip(),
            "zip": zip_code,
            "is_online": city.str.upper().eq("ONLINE").fillna(False),
            "mcc_code": _int(df["mcc"], "int64"),
            "errors": errors,
            "has_error": errors.notna(),
        }
    )
    return out


CLEANERS = {
    "users": clean_users,
    "cards": clean_cards,
    "mcc_codes": clean_mcc_codes,
    "fraud_labels": clean_fraud_labels,
    "transactions": clean_transactions,
}


def build_silver(tables: list[str] | None = None) -> pd.DataFrame:
    """Clean every bronze table into data/silver/<table>.parquet and return a row log."""
    from ingestion import read_bronze

    config.ensure_dirs()
    log = []
    for table in tables or list(CLEANERS):
        bronze = read_bronze(table)
        silver = CLEANERS[table](bronze)
        silver.to_parquet(config.SILVER_DIR / f"{table}.parquet", index=False)
        log.append({"table": table, "bronze_rows": len(bronze), "silver_rows": len(silver),
                    "silver_columns": silver.shape[1]})
        del bronze, silver
    return pd.DataFrame(log)


def read_silver(table: str) -> pd.DataFrame:
    return pd.read_parquet(config.SILVER_DIR / f"{table}.parquet")

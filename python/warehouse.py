"""DuckDB access to the local medallion cache.

Silver and gold Parquet files are exposed as views named ``silver_<table>`` /
``gold_<table>``, so the SQL in ``sql/`` reads like ordinary warehouse SQL and
DuckDB scans the Parquet files directly without loading them into pandas.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

import config


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    refresh_views(con)
    return con


def refresh_views(con: duckdb.DuckDBPyConnection) -> None:
    for layer, folder in (("silver", config.SILVER_DIR), ("gold", config.GOLD_DIR)):
        for path in sorted(Path(folder).glob("*.parquet")):
            con.execute(
                f"CREATE OR REPLACE VIEW {layer}_{path.stem} AS "
                f"SELECT * FROM read_parquet('{path.as_posix()}')"
            )


def sql_text(relative_path: str) -> str:
    return (config.SQL_DIR / relative_path).read_text().strip().rstrip(";")


def query(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


def run_sql_file(con: duckdb.DuckDBPyConnection, relative_path: str) -> pd.DataFrame:
    return query(con, sql_text(relative_path))


def build_gold(con: duckdb.DuckDBPyConnection, name: str, relative_path: str) -> pd.DataFrame:
    """Run a gold SQL model, write data/gold/<name>.parquet, register it as gold_<name>."""
    config.ensure_dirs()
    out = config.GOLD_DIR / f"{name}.parquet"
    con.execute(f"COPY ({sql_text(relative_path)}) TO '{out.as_posix()}' (FORMAT PARQUET)")
    refresh_views(con)
    return query(con, f"SELECT COUNT(*) AS rows FROM gold_{name}")


def write_gold(con: duckdb.DuckDBPyConnection, name: str, df: pd.DataFrame) -> None:
    """Persist a pandas result (e.g. model output) as a gold table."""
    config.ensure_dirs()
    df.to_parquet(config.GOLD_DIR / f"{name}.parquet", index=False)
    refresh_views(con)

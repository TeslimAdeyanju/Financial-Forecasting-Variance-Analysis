"""Stage 2: pull the five source files from OneDrive and land them in bronze.

Bronze keeps every value as text exactly as published. The only reshaping is
turning the two JSON dictionaries into two-column tables so they can be stored
as Parquet. All typing and cleaning happens in stage 3 (``cleaning.py``).
"""
from __future__ import annotations

import time
from io import BytesIO

import pandas as pd
import requests

import config

CHUNK_BYTES = 32 * 1024 * 1024
MAX_RETRIES = 5


def _from_onedrive(filename: str, **kwargs) -> pd.DataFrame:
    from onedrive_loader import load  # imported lazily so stages 3-6 don't need credentials

    return load(config.ONEDRIVE_FOLDER, filename, **kwargs)


def _download_resumable(filename: str) -> BytesIO:
    """Download a large OneDrive file into memory in ranged chunks, retrying failed chunks.

    onedrive_loader.load() fetches a file in one GET, and on the ~1.2 GB transactions
    file the connection was reset part-way through. This asks Graph for the item's
    pre-authenticated download URL, then requests it in byte ranges, so a dropped
    connection costs one chunk rather than the whole transfer. Nothing is written to disk.
    """
    from urllib.parse import quote

    import onedrive_loader as od  # uses the connector's credentials and folder settings

    path = quote(od._onedrive_path(f"{config.ONEDRIVE_FOLDER}/{filename}"), safe="/")
    meta_url = f"https://graph.microsoft.com/v1.0/users/{quote(od.USER_EMAIL, safe='@')}/drive/root:/{path}"

    def item_meta() -> dict:
        r = requests.get(meta_url, headers={"Authorization": f"Bearer {od._get_token()}"}, timeout=60)
        r.raise_for_status()
        return r.json()

    meta = item_meta()
    size, download_url = meta["size"], meta["@microsoft.graph.downloadUrl"]
    buffer = BytesIO()
    while buffer.tell() < size:
        start = buffer.tell()
        end = min(start + CHUNK_BYTES, size) - 1
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = requests.get(download_url, headers={"Range": f"bytes={start}-{end}"}, timeout=120)
                if r.status_code in (401, 403):  # pre-authenticated URL expired: fetch a fresh one
                    download_url = item_meta()["@microsoft.graph.downloadUrl"]
                    raise requests.HTTPError(f"download URL expired ({r.status_code})")
                r.raise_for_status()
                if len(r.content) != end - start + 1:
                    raise requests.HTTPError(f"short read: {len(r.content)} of {end - start + 1} bytes")
                buffer.write(r.content)
                break
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
                if attempt == MAX_RETRIES:
                    raise
                print(f"  chunk at {start / 1e6:,.0f} MB failed ({exc}); retry {attempt}/{MAX_RETRIES - 1}")
                time.sleep(2 * attempt)
    buffer.seek(0)
    return buffer


def _dict_to_table(df: pd.DataFrame, key: str, value: str) -> pd.DataFrame:
    """JSON {key: value} loaded with keys as the index -> two text columns."""
    out = df.iloc[:, 0].rename(value).rename_axis(key).reset_index()
    return out.astype("string")


def fetch(table: str) -> pd.DataFrame:
    filename, kwargs = config.SOURCES[table]
    if table == "mcc_codes":
        return _dict_to_table(_from_onedrive(filename, **kwargs), "mcc", "description")
    if table == "fraud_labels":
        # {"target": {"<transaction id>": "Yes"|"No", ...}} -> index = transaction id
        return _dict_to_table(_from_onedrive(filename, **kwargs), "transaction_id", "target")
    if table == "transactions":
        # ~1.2 GB CSV: resumable ranged download, then the pyarrow engine keeps peak memory manageable
        return pd.read_csv(_download_resumable(filename), dtype=str, engine="pyarrow")
    return _from_onedrive(filename, dtype=str)


def ingest_all(tables: list[str] | None = None, refresh: bool = False) -> pd.DataFrame:
    """Fetch each source, write data/bronze/<table>.parquet, return a load log.

    Tables already in bronze are reused unless refresh=True, so an interrupted run
    resumes without re-downloading what already landed.
    """
    import pyarrow.parquet as pq

    config.ensure_dirs()
    log = []
    for table in tables or list(config.SOURCES):
        start = time.perf_counter()
        path = config.BRONZE_DIR / f"{table}.parquet"
        reused = path.exists() and not refresh
        if reused:
            meta = pq.ParquetFile(path).metadata
            rows, columns = meta.num_rows, meta.num_columns
        else:
            df = fetch(table)
            tmp = path.with_suffix(".parquet.tmp")
            df.to_parquet(tmp, index=False)
            tmp.replace(path)  # atomic: a crash never leaves a half-written bronze file
            rows, columns = df.shape
            del df
        log.append(
            {
                "table": table,
                "source_file": config.SOURCES[table][0],
                "rows": rows,
                "expected_rows": config.EXPECTED_ROWS.get(table),
                "columns": columns,
                "action": "reused cache" if reused else "loaded from OneDrive",
                "seconds": round(time.perf_counter() - start, 1),
                "parquet_mb": round(path.stat().st_size / 1e6, 1),
            }
        )
    out = pd.DataFrame(log)
    out["rows_match"] = out["rows"] == out["expected_rows"]
    return out


def read_bronze(table: str) -> pd.DataFrame:
    return pd.read_parquet(config.BRONZE_DIR / f"{table}.parquet")

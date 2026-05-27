"""
Upload local Bronze JSONs in to Databricks' Unity Catalog Volumes.

Walks the local Bronze tree at fintech_datalake/bronze/<source>/<endpoint>/<ticker>.json
and uploads each file to its mirrored path under
        /Volumes/ingestion/<source>/raw_jsons/<endpoint>/<ticker>.json in the Databricks workspace.
Idempotent: re-uploads overwrite existing volume files
(safe because Bronze COPY INTO downstream tracks processed files, not file timestamps).

Authentication: reads DATABRICKS_HOST + DATABRICKS_TOKEN from the project .env via
python-dotenv. SDK picks these up automatically when WorkspaceClient() is constructed.
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Repo-relative root for local Bronze JSONs. Resolved at import time from this file's location
# so the script runs correctly from any CWD.
_REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_BRONZE_ROOT = _REPO_ROOT / "fintech_datalake" / "bronze"

# UC target. Catalog is ingestion (per ADR-0016 + TF state); each source has a raw_jsons volume.
UC_CATALOG = "ingestion"
UC_VOLUME = "raw_jsons"

@dataclass(frozen=True)
class UploadPlan:
    """One file to upload. Built by iter_local_jsons(); consumed by upload_one().

    `ticker` + `batch_date` mirror save_to_lake()'s producer-side schema in
    fintech_datalake/scripts/utils.py — the local filename is f"{ticker}_{batch_date}.json".
    """
    local_path: Path
    source: str        # "alpha_vantage" | "fmp"
    endpoint: str      # e.g. "profile", "time_series_daily"
    ticker: str        # e.g. "AAPL"
    batch_date: str    # YYYYMMDD, e.g. "20260521"
    volume_path: str   # /Volumes/ingestion/<source>/raw_jsons/<endpoint>/<ticker>_<batch_date>.json

def volume_path_for(source: str, endpoint: str, ticker: str, batch_date: str) -> str:
    """
    Map (source, endpoint, ticker, batch_date) to the UC Volume URI.

    Mirrors the local layout produced by save_to_lake():
        <lake>/<source>/<endpoint>/<ticker>_<batch_date>.json
        → /Volumes/ingestion/<source>/raw_jsons/<endpoint>/<ticker>_<batch_date>.json
    """
    return f"/Volumes/{UC_CATALOG}/{source}/{UC_VOLUME}/{endpoint}/{ticker}_{batch_date}.json"

def iter_local_jsons(root: Path = LOCAL_BRONZE_ROOT) -> Iterator[UploadPlan]:
    """
    Yield one UploadPlan per local Bronze JSON.

    Expected layout: <root>/<source>/<endpoint>/<ticker>_<YYYYMMDD>.json
    Files that don't match are skipped with a warning (stray .tmp, audit logs, etc.).
    """
    if not root.is_dir():
        raise FileNotFoundError(f"Local Bronze root not found: {root}")

    for json_path in sorted(root.rglob("*.json")):
        rel = json_path.relative_to(root)
        parts = rel.parts
        if len(parts) != 3:
            logger.warning("skipping unexpected path shape: %s", rel)
            continue
        source, endpoint, filename = parts
        stem = filename.removesuffix(".json")
        if "_" not in stem:
            logger.warning("skipping filename without _<batch_date>: %s", rel)
            continue
        ticker, batch_date = stem.rsplit("_", 1)
        if not (len(batch_date) == 8 and batch_date.isdigit()):
            logger.warning("skipping non-YYYYMMDD suffix: %s", rel)
            continue
        yield UploadPlan(
            local_path=json_path,
            source=source,
            endpoint=endpoint,
            ticker=ticker,
            batch_date=batch_date,
            volume_path=volume_path_for(source, endpoint, ticker, batch_date),
        )

def upload_one(client, plan: UploadPlan) -> None:
    """
    Upload one local JSON to its UC Volume path. Raises on SDK error.
    """
    with plan.local_path.open("rb") as fh:
        client.files.upload(plan.volume_path, fh, overwrite=True)

def run(plans: Iterator[UploadPlan], *, dry_run: bool = False) -> tuple[int, int]:
    """
    Drive uploads for every plan. Returns (succeeded, failed) counts.

    Per-file errors are caught, logged, and counted — they never abort the batch.
    Dry-run skips SDK construction entirely so it works without credentials.
    """
    client = None
    if not dry_run:
        from databricks.sdk import WorkspaceClient
        client = WorkspaceClient()

    succeeded = failed = 0
    for plan in plans:
        if dry_run:
            logger.info("[dry] %s -> %s", plan.local_path.name, plan.volume_path)
            succeeded += 1
            continue
        try:
            upload_one(client, plan)
        except Exception as exc:
            failed += 1
            logger.error("FAIL %s -> %s: %s", plan.local_path.name, plan.volume_path, exc)
        else:
            succeeded += 1
            logger.info("OK   %s -> %s", plan.local_path.name, plan.volume_path)

    logger.info("done: %d succeeded, %d failed", succeeded, failed)
    return succeeded, failed      

def main() -> int:
    """CLI entry point: filter local Bronze JSONs by flags, then upload (or dry-run)."""
    import argparse
    from itertools import islice

    parser = argparse.ArgumentParser(description="Upload local Bronze JSONs to UC volumes.")
    parser.add_argument("--dry-run", action="store_true", help="log planned uploads, hit no API")
    parser.add_argument("--source", help="restrict to one source dir, e.g. fmp")
    parser.add_argument("--endpoint", help="restrict to one endpoint dir, e.g. profile")
    parser.add_argument("--ticker", help="restrict to one ticker (case-insensitive)")
    parser.add_argument("--limit", type=int, help="stop after N files")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    load_dotenv()

    plans = iter_local_jsons()
    if args.source:
        plans = (p for p in plans if p.source == args.source)
    if args.endpoint:
        plans = (p for p in plans if p.endpoint == args.endpoint)
    if args.ticker:
        wanted = args.ticker.upper()
        plans = (p for p in plans if p.ticker == wanted)
    if args.limit is not None:
        plans = islice(plans, args.limit)

    succeeded, failed = run(plans, dry_run=args.dry_run)
    return 0 if failed == 0 else 1

if __name__ == "__main__":
     sys.exit(main())
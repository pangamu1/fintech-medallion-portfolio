"""
    I/O primitives for the ingestion scripts 

    Provides:
        - save_to_lake: atomic JSON write with a metadata wrapper, into bronze
        - log_run: one line JSONL append for ingestion event
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

def save_to_lake(
        data: dict,
        source: str,
        endpoint_name: str,
        ticker: str,
        *,
        lake_path: Path,
) -> Path:
    """
    Write raw API response to the Bronze Lake with a metadata wrapper.

    Final Path: {lake_path}/{source}/{endpoint_name}/{ticker}_{YYYYMMDD}.json
    Atomic: writes to a .tmp sibling first, then rename into place. 

    Returns the final Path on success.
    """
    now = datetime.now(timezone.utc)
    batch_date = now.strftime("%Y%m%d")

    folder = lake_path / source / endpoint_name
    folder.mkdir(parents=True, exist_ok=True)

    final_path = folder / f"{ticker}_{batch_date}.json"
    tmp_path = final_path.with_suffix(".json.tmp")

    payload = {
        "_ingest_timestamp": now.isoformat(),
        "_source": source,
        "_endpoint": endpoint_name,
        "_ticker": ticker,
        "_batch_date": batch_date,
        "data": data,
    }

    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    tmp_path.rename(final_path)

    logger.info("Saved %s/%s/%s -> %s", source, endpoint_name, ticker, final_path)
    return final_path

def log_run(
        *,
        log_path: Path,
        ticker: str,
        source: str,
        endpoint: str,
        status: str,
        error: str | None = None,
) -> None:
    """
    Append a single ingestiion event to the JSONL log file.

    One JSON object per line, terminated by '\\n'. Append-Only.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "source": source,
        "endpoint": endpoint,
        "status": status,
        "error": error,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")
"""
Fetch data from Financial Modeling Prep(FMP) and land the raw JSON in Bronze.
"""
import json
import logging
import time


import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config
import utils

logging.basicConfig(level=logging.INFO, format="%(name)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# FMP free tier 250 calls/day, no documented per-,minute ceiling.
# 0.5s pacing is defensive politeness, not a strict requirement. 100 calls x 0.5s.
# = 50s overhead on the full run; per-call latency is the dominant cost anyway. 
_FMP_SECONDS_BETWEEN_CALLS = 0.5

def _log(ticker: str, endpoint_name: str, status: str, error: str | None = None) -> None:
    """
    Local helper - wraps utils.log_run with this module's constants baked in.
    """
    utils.log_run(
        log_path=config.INGESTION_LOG_PATH,
        ticker=ticker,
        source="fmp",
        endpoint=endpoint_name,
        status=status,
        error=error,
    )
def _build_session() -> requests.Session:
    """
    Create a session with retry-on-transient-errors + exponential backoff.

    Retries: 3 attempts on 429/500/502/503/504.
    Backoff: 1s, 2s, 4s between those retries.
    Only retries GET (idempotent).
    """
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session

def main() -> None:
    session = _build_session()

    for ticker in config.TICKERS:
        for endpoint in config.FMP_ENDPOINTS:
            endpoint_name = endpoint["name"]
            url = f"{config.FMP_BASE}/{endpoint['path']}"
            params = {
                "symbol": ticker,
                "apikey": config.FMP_API_KEY
            }

            logger.info("Fetching %s %s from FMP", ticker, endpoint_name)

            try:
                response = session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                logger.error("Request/parse failed for %s/%s: %s",
                             ticker, endpoint_name, e)
                _log(ticker, endpoint_name, "error", str(e))
            else:
                if isinstance(data, list) and len(data) == 0:
                    logger.warning("FMP returned empty list for %s/%s — symbol may be outside allowlist for this endpoint",
                                   ticker, endpoint_name)
                    _log(ticker, endpoint_name, "empty", "0 records returned")
                elif isinstance(data, dict) and "Error Message" in data:
                    logger.warning("FMP error for %s/%s: %s",
                                   ticker, endpoint_name, data["Error Message"])
                    _log(ticker, endpoint_name, "error_in_body", data["Error Message"])
                else:
                    saved = utils.save_to_lake(
                        data=data,
                        source="fmp",
                        endpoint_name=endpoint_name,
                        ticker=ticker,
                        lake_path=config.BRONZE_PATH,
                    )
                logger.info("Bronze file: %s (%d bytes)",
                                saved, saved.stat().st_size)
                _log(ticker, endpoint_name, "success")
            
            time.sleep(_FMP_SECONDS_BETWEEN_CALLS)


if __name__ == "__main__":
    main()

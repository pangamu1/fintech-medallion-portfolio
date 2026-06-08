"""
Fetch data from Alpha Vantage and land the raw JSON in Bronze.
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
# AV free tier allows N requests/minute. Sleep (60/N + 1s margin) between calls to stay under the burst ceiling.
_AV_SECONDS_BETWEEN_CALLS = 60.0 / config.ALPHA_VANTAGE_RATE_LIMIT_PER_MINUTE + 1.0
logger = logging.getLogger(__name__)

def _log(ticker: str, endpoint_name: str, status: str, error: str | None = None) -> None:
    """
    Local helper - wraps utils.log_runwith this module's constants baked in.

    All ingest alpha_vantage rows in INGESTION_LOG_PATH share source='alpha_vantage'
    and the same log_path. This helper removes the boilerplate at 3 call sites. 
    """
    utils.log_run(
        log_path=config.INGESTION_LOG_PATH,
        ticker=ticker,
        source='alpha_vantage',
        endpoint=endpoint_name,
        status=status,
        error=error,
    )

def _build_session() -> requests.session:
    """Create a Session with retry-on-transient-errors + exponential backoff.

    Retries: 3 attempts on 429/500/502/503/504.
    Backoff: 1s, 2s, 4s between retries (Retry's exponential schedule).
    Only retries GET (idempotent).
    """
    session = requests.Session()
    retry = Retry(
        total = 3,
        backoff_factor= 1.0,
        status_forcelist=(429,500,502,503,504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session

def main() -> None:
    endpoint = config.AV_ENDPOINTS[0]
    session = _build_session()

    for ticker in config.TICKERS:
        params = {
            "function": endpoint["function"],
            "symbol": ticker,
            "outputsize": config.AV_OUTPUTSIZE, 
            "apikey": config.alpha_vantage_api_key(),
        }

        logger.info("Fetching %s %s from Alpha Vantage", ticker, endpoint["function"])

        try:
            response = session.get(config.ALPHA_VANTAGE_BASE, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            logger.error("Request/parse failed for %s/%s: %s",
                         ticker, endpoint["function"], e)
            _log(ticker, endpoint["name"], "error", str(e))
        else:
            if "Information" in data or "Note" in data:
                message = data.get("Information") or data.get("Note")
                logger.warning(
                    "AV throttle/premium response for %s/%s: %s",
                    ticker, endpoint["function"], message,
                )
                _log(ticker, endpoint["name"], "throttled", message)
            else:
                saved = utils.save_to_lake(
                    data=data,
                    source="alpha_vantage",
                    endpoint_name=endpoint["name"],
                    ticker=ticker,
                    lake_path=config.BRONZE_PATH,
                )
                logger.info("Bronze file: %s (%d bytes)", saved, saved.stat().st_size)
                _log(ticker, endpoint["name"], "success")
        time.sleep(_AV_SECONDS_BETWEEN_CALLS)   

if __name__ == "__main__":
    main()


"""
Project wide configuration.

Side Effect: Importing this module loads .env into os.environ exactly once
All ingestion scripts imports constants from here. 
"""
from pathlib import Path
from dotenv import load_dotenv
import os
from typing import TypedDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Parents[2] coz fintech_datalake directory is [1] and scripts directory is [0]

load_dotenv(PROJECT_ROOT / ".env")

def _required_env(key: str) -> str:
    "Read a required environment variable. Raise with a clear message if missing or empty."
    value = os.environ.get(key)

    if not value:
        raise RuntimeError(
            f"Required Environment variable {key!r} is missing or empty."
            f"See .env.example for the expected schema and copy it to .env"
        )
    return value

ALPHA_VANTAGE_API_KEY = _required_env("ALPHA_VANTAGE_API_KEY")
FMP_API_KEY = _required_env("FMP_API_KEY")

# The 10 Tickers Universe
TICKERS: list[str] = [
    "AAPL", "MSFT", "AMZN", "META", "TSLA",
    "JPM", "JNJ", "NVDA", "GOOGL", "PYPL",
]

# API Base URLs:
ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
FMP_BASE = "https://financialmodelingprep.com/stable"

# Data Lake paths:
DATA_LAKE_PATH = PROJECT_ROOT / "fintech_datalake"
BRONZE_PATH = DATA_LAKE_PATH / "bronze"
LOGS_PATH = DATA_LAKE_PATH / "logs"
# Single source of truth for the ingestion log location
INGESTION_LOG_PATH = LOGS_PATH / "ingestion_log.jsonl"

# === Endpoint Catalogs ===

class AVEndpoint(TypedDict):
    """Alpha Vantage Endpoint Metadata"""
    name: str           # canonical lowercase name (Bronze Folder + Log Key)
    function: str       # AV API "function" parameter (UPPERCASE per AV convention)
    description: str    # one-line human description

class FMPEndpoint(TypedDict):
    """FMP Endpoint Metadata"""
    name: str           # canonical lowercase name (Bronze Folder + Log Key)
    path: str           # FMP URL path component (kebab-case per FMP convention)
    description: str    # one-line human description

AV_ENDPOINTS: list[AVEndpoint] = [
    {
        "name": "time_series_daily",
        "function": "TIME_SERIES_DAILY",
        "description": "Last 100 trading days OHLCV (compact); cross-validation vs FMP",
    },
]

# FMP Endpoints 
FMP_ENDPOINTS: list[FMPEndpoint] = [
    {
        "name": "profile",
        "path": "profile",
        "description": "Company snapshot — sector, industry, market cap, exchange, employees, IPO date (no allowlist)",
    },
    {
        "name": "historical_price_full",
        "path": "historical-price-eod/full",
        "description": "Full historical OHLCV + change + vwap (raw, not adjusted)",
    },
    {
        "name": "historical_price_adjusted",
        "path": "historical-price-eod/dividend-adjusted",
        "description": "Split + dividend adjusted OHLCV (for total-return analysis)",
    },
    {
        "name": "income_statement",
        "path": "income-statement",
        "description": "Quarterly + annual income statement (capped 5/call on free)",
    },
    {
        "name": "balance_sheet",
        "path": "balance-sheet-statement",
        "description": "Quarterly assets, liabilities, equity (capped 5/call on free)",
    },
    {
        "name": "cash_flow",
        "path": "cash-flow-statement",
        "description": "Quarterly operating/investing/financing cash flows (capped 5/call on free)",
    },
    {
        "name": "key_metrics",
        "path": "key-metrics",
        "description": "Annual ratios (P/E, ROE, debt/equity, FCF); free tier annual-only, capped 5/call",
    },
    {
        "name": "earnings",
        "path": "earnings",
        "description": "EPS actual vs estimated; future-dated rows have null actuals (late-arriving pattern)",
    },
    {
        "name": "dividends",
        "path": "dividends",
        "description": "Dividend events — declaration / record / payment dates + amount + yield (capped 5/call)",
    },
    {
        "name": "splits",
        "path": "splits",
        "description": "Stock split events — numerator/denominator per split date (capped 5/call)",
    },
]

# === Alpha Vantage TIME_SERIES_DAILY output size ===
# Free tier supports only last 100 trading days.
AV_OUTPUTSIZE = "compact"

# === Free-tier rate limits ===
ALPHA_VANTAGE_RATE_LIMIT_PER_MINUTE = 5
ALPHA_VANTAGE_RATE_LIMIT_PER_DAY = 25
FMP_RATE_LIMIT_PER_DAY = 250

# === SEC EDGAR (Form 4 insider transactions) — keyless, politeness-gated ===
# SEC fair-access REQUIRES a descriptive User-Agent carrying a real contact
# email; requests without one get 403. It is NOT a secret (broadcast on every
# call) — so it lives here as a plain constant, never in .env.

SEC_USER_AGENT = "fintech-medallion-portfolio piruthviraj7@gmail.com"

# Multi-hop API: (1) ticker->CIK map, (2) per-CIK filing history, (3) Form 4 doc.
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_BASE = "https://data.sec.gov/submissions"      # + /CIK{cik10}.json
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"  # + /{cik}/{accession_nodash}/{doc}

# Only Form 4 (insider transactions); 4/A amendments deferred (CP0 decision 2).
SEC_FORM_TYPE = "4"

# Backfill window: most recent N Form 4 per ticker (CP0 decision 2; FMP-5-cap spirit).
SEC_MAX_FILINGS_PER_TICKER = 30

# SEC fair-access ceiling is 10 req/s; the client paces well under it.
SEC_RATE_LIMIT_PER_SECOND = 10

# Bronze disk + table name for the landed JSON (source="sec").
SEC_ENDPOINT_NAME = "insider_transactions"
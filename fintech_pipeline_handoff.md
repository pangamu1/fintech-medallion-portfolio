# FinTech Stock Market — Dimensional Modeling Portfolio Project
### Handoff Document for Claude Code

---

## 1. Project Summary

**What we are building:**
A end-to-end data engineering pipeline that ingests raw stock market and financial data from two free public APIs, lands it in a local Data Lake (folder-based), and processes it through a Medallion Architecture (Bronze → Silver → Gold) hosted on Databricks Free Edition. The Gold layer exposes a clean Star Schema dimensional model ready for BI analysts, quant researchers, and executive dashboards.

**Why this exists:**
This is a portfolio project designed to demonstrate production-grade data engineering concepts in a FinTech domain. The dataset is intentionally chosen for its messiness, schema inconsistencies, and real-world complexity — so that every concept (SCD2, CDC, schema evolution, schema enforcement, late-arriving data) is exercised meaningfully, not artificially.

**The business problem being solved:**
A FinTech company generates enormous volumes of raw market and financial data daily from multiple inconsistent external sources. None of that raw data is directly usable for investment decisions. This pipeline bridges the gap — making data clean, trusted, historically accurate, and query-ready for downstream consumers.

---

## 2. Role Definition

### Your Role: Data Engineer
You sit at the center of the data flow. You do not analyze data or make investment decisions. Your job is to make it possible for others to do those things reliably.

You own:
- The ingestion pipeline (Python scripts hitting external APIs)
- The local Data Lake folder structure (acts as a simulated cloud storage)
- The full Medallion Architecture in Databricks (Bronze → Silver → Gold)
- Data quality guarantees to all downstream consumers

### Upstream (outside your control)
| Source | What they provide | Why it is messy |
|---|---|---|
| Alpha Vantage API | OHLCV price data, technicals, earnings, company overview | `"None"` strings instead of nulls, inconsistent field names across endpoints, date-keyed dict format |
| FMP (Financial Modeling Prep) API | Income statements, balance sheets, cash flow, key metrics, insider trades, earnings surprises | Incorrect earnings figures reported by users, delayed EOD updates, inconsistent date formats between `transactionDate` and `filingDate` |

### Downstream (your consumers)
| Consumer | What they need from you | Which Gold tables they use |
|---|---|---|
| BI Analyst | Clean, stable, pre-joined tables — no nulls, consistent column names, query-ready | `fact_stock_daily`, `dim_company`, `dim_date` |
| Quant Analyst | Historically accurate data — correct split-adjusted prices, SCD2 integrity, late-arriving facts handled properly | `fact_earnings_event`, `fact_stock_daily`, `dim_company` (SCD2) |
| Executive / Portfolio Manager | Aggregated, business-readable summaries via dashboard | All Gold tables via pre-built views |

---

## 3. Data Sources

### API 1 — Alpha Vantage (Price & Market Data)
- **Sign-up required:** Yes (free, instant)
- **Free tier:** 25 requests/day, 5 requests/minute
- **Base URL:** `https://www.alphavantage.co/query`
- **Key endpoints to use:**

| Function | What it returns | Calls per ticker |
|---|---|---|
| `TIME_SERIES_DAILY` | 20+ years of daily OHLCV | 1 |
| `COMPANY_OVERVIEW` | Fundamentals snapshot, sector, P/E, 52-week range | 1 |
| `EARNINGS` | Quarterly and annual EPS history | 1 |
| `INCOME_STATEMENT` | Annual and quarterly income statement | 1 |
| `BALANCE_SHEET` | Annual and quarterly balance sheet | 1 |

- **Known data quality issues to handle in Bronze → Silver:**
  - Fields like `DividendYield`, `ForwardPE`, `AnalystTargetPrice` return `"None"` as a string, not JSON null
  - Date keys are returned newest-first as a dictionary (not an array)
  - Field naming inconsistency: `"4. close"` vs `"close"` vs `"adjusted close"` depending on endpoint
  - Earnings dates do not always align to trading calendar days

### API 2 — FMP (Financial Modeling Prep) (Fundamentals & Events)
- **Sign-up required:** Yes (free, instant)
- **Free tier:** 250 requests/day
- **Base URL:** `https://financialmodelingprep.com/stable/`
- **Key endpoints to use:**

| Endpoint | What it returns | Calls per ticker |
|---|---|---|
| `income-statement` | Quarterly + annual income statement, GAAP standardized | 1 |
| `balance-sheet-statement` | Assets, liabilities, equity by quarter | 1 |
| `cash-flow-statement` | Operating, investing, financing cash flows | 1 |
| `historical-price-full` | EOD OHLCV with dividends and splits adjusted | 1 |
| `key-metrics` | PE ratio, ROE, debt-to-equity, market cap by quarter | 1 |
| `insider-trading` | Insider buy/sell transactions with role and date | 1 |
| `earnings-surprises` | Actual vs estimated EPS, surprise percentage | 1 |

- **Known data quality issues to handle in Bronze → Silver:**
  - `reportedEPS` vs `estimatedEPS` discrepancies require enrichment logic
  - `transactionDate` and `filingDate` use different formats in insider trading endpoint
  - Quarterly filings have null values for fields that exist in other quarters (schema variation)
  - Some EOD updates are delayed — late-arriving records are expected

### Daily API Budget
- Total free calls available: 275/day (25 Alpha Vantage + 250 FMP)
- Self-imposed limit for learning pace: ~10 meaningful pulls per session
- Each `TIME_SERIES_DAILY` call returns the **full 20-year history** in one hit — use this wisely

---

## 4. Target Tickers (10 Companies)

Deliberately chosen across sectors to create natural schema variation and real SCD2 events:

| Ticker | Company | Why chosen for modeling |
|---|---|---|
| `AAPL` | Apple | Large cap stable baseline |
| `MSFT` | Microsoft | Cloud transition visible in multi-year financials |
| `AMZN` | Amazon | Retail + AWS split complicates income statement schema |
| `META` | Meta | Sector reclassification (Tech → Communication Services 2018) — natural SCD2 event |
| `TSLA` | Tesla | High volatility — extreme price swings, interesting fact table |
| `JPM` | JPMorgan | Bank — different income statement schema than tech companies |
| `JNJ` | Johnson & Johnson | Kenvue spinoff (2023) — corporate action SCD2 event |
| `NVDA` | Nvidia | 10-for-1 stock split (2024) — tests split-adjusted price logic |
| `BRK-B` | Berkshire Hathaway | No dividends ever — tests null handling in dividend fields |
| `GOOG` | Alphabet | Dual class share structure — interesting for company dimension |

---

## 5. Local Data Lake Structure

Simulate a cloud Data Lake using local folders. This is what gets manually uploaded to Databricks.

```
fintech_datalake/
│
├── bronze/
│   ├── alpha_vantage/
│   │   ├── daily_prices/
│   │   │   └── AAPL_20250512.json
│   │   ├── company_overview/
│   │   │   └── AAPL_20250512.json
│   │   └── earnings/
│   │       └── AAPL_20250512.json
│   └── fmp/
│       ├── income_statement/
│       │   └── AAPL_20250512.json
│       ├── key_metrics/
│       │   └── AAPL_20250512.json
│       └── insider_trading/
│           └── AAPL_20250512.json
│
├── silver/          ← populated after Databricks transformations
│
├── gold/            ← populated after Databricks transformations
│
├── logs/
│   └── ingestion_log.json
│
└── scripts/
    ├── ingest_alpha_vantage.py
    ├── ingest_fmp.py
    ├── utils.py
    └── config.py
```

**Naming convention:** `{TICKER}_{YYYYMMDD}.json`
All raw files are append-only — never overwrite, always add a new dated file.

---

## 6. Python Ingestion Scripts

### config.py
```python
ALPHA_VANTAGE_API_KEY = "YOUR_KEY_HERE"
FMP_API_KEY = "YOUR_KEY_HERE"

TICKERS = ["AAPL", "MSFT", "AMZN", "META", "TSLA", "JPM", "JNJ", "NVDA", "BRK-B", "GOOG"]

ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
FMP_BASE = "https://financialmodelingprep.com/stable"

DATA_LAKE_PATH = "./fintech_datalake/bronze"
LOG_PATH = "./fintech_datalake/logs/ingestion_log.json"
```

### utils.py
```python
import os, json, logging
from datetime import datetime

def save_to_lake(data: dict, source: str, endpoint: str, ticker: str, lake_path: str):
    today = datetime.utcnow().strftime("%Y%m%d")
    folder = os.path.join(lake_path, source, endpoint)
    os.makedirs(folder, exist_ok=True)
    filename = os.path.join(folder, f"{ticker}_{today}.json")
    payload = {
        "_ingest_timestamp": datetime.utcnow().isoformat(),
        "_source": source,
        "_endpoint": endpoint,
        "_ticker": ticker,
        "_batch_date": today,
        "data": data
    }
    with open(filename, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[OK] Saved: {filename}")
    return filename

def log_run(log_path: str, ticker: str, source: str, endpoint: str, status: str, error: str = None):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "ticker": ticker,
        "source": source,
        "endpoint": endpoint,
        "status": status,
        "error": error
    }
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logs = []
    if os.path.exists(log_path):
        with open(log_path) as f:
            logs = json.load(f)
    logs.append(entry)
    with open(log_path, "w") as f:
        json.dump(logs, f, indent=2)
```

### ingest_alpha_vantage.py
```python
import time, requests
from config import ALPHA_VANTAGE_API_KEY, ALPHA_VANTAGE_BASE, TICKERS, DATA_LAKE_PATH, LOG_PATH
from utils import save_to_lake, log_run

ENDPOINTS = [
    {"function": "TIME_SERIES_DAILY", "outputsize": "full"},
    {"function": "COMPANY_OVERVIEW"},
    {"function": "EARNINGS"},
]

def fetch(params: dict) -> dict:
    params["apikey"] = ALPHA_VANTAGE_API_KEY
    response = requests.get(ALPHA_VANTAGE_BASE, params=params, timeout=30)
    response.raise_for_status()
    return response.json()

def ingest(tickers: list = TICKERS):
    for ticker in tickers:
        for ep in ENDPOINTS:
            fn = ep["function"]
            params = {**ep, "symbol": ticker}
            try:
                data = fetch(params)
                # Detect rate limit response from Alpha Vantage
                if "Note" in data or "Information" in data:
                    print(f"[WARN] Rate limit hit for {ticker}/{fn}. Sleeping 60s.")
                    time.sleep(60)
                    data = fetch(params)
                save_to_lake(data, "alpha_vantage", fn.lower(), ticker, DATA_LAKE_PATH)
                log_run(LOG_PATH, ticker, "alpha_vantage", fn, "success")
            except Exception as e:
                print(f"[ERROR] {ticker}/{fn}: {e}")
                log_run(LOG_PATH, ticker, "alpha_vantage", fn, "error", str(e))
            time.sleep(13)  # Stay within 5 calls/minute limit

if __name__ == "__main__":
    ingest()
```

### ingest_fmp.py
```python
import time, requests
from config import FMP_API_KEY, FMP_BASE, TICKERS, DATA_LAKE_PATH, LOG_PATH
from utils import save_to_lake, log_run

ENDPOINTS = [
    "income-statement",
    "balance-sheet-statement",
    "cash-flow-statement",
    "key-metrics",
    "insider-trading",
    "earnings-surprises",
    "historical-price-full",
]

def fetch(endpoint: str, ticker: str) -> dict:
    url = f"{FMP_BASE}/{endpoint}"
    params = {"symbol": ticker, "apikey": FMP_API_KEY, "limit": 40}
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()

def ingest(tickers: list = TICKERS):
    for ticker in tickers:
        for ep in ENDPOINTS:
            try:
                data = fetch(ep, ticker)
                save_to_lake({"results": data}, "fmp", ep.replace("-", "_"), ticker, DATA_LAKE_PATH)
                log_run(LOG_PATH, ticker, "fmp", ep, "success")
            except Exception as e:
                print(f"[ERROR] {ticker}/{ep}: {e}")
                log_run(LOG_PATH, ticker, "fmp", ep, "error", str(e))
            time.sleep(1)

if __name__ == "__main__":
    ingest()
```

---

## 7. Medallion Architecture

```
┌─────────────────┐     ┌─────────────────┐
│  Alpha Vantage  │     │      FMP        │
│  OHLCV · techs  │     │  Fundamentals   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └──────────┬────────────┘
                    ▼
         ┌──────────────────┐
         │   Local Data     │
         │   Lake (JSON)    │
         │  Bronze folders  │
         └────────┬─────────┘
                  │  Manual upload
                  ▼
    ┌─────────────────────────────┐
    │         Databricks          │
    │                             │
    │  ┌───────────────────────┐  │
    │  │       BRONZE          │  │
    │  │  Raw · append-only    │  │
    │  │  Schema evolution ON  │  │
    │  │  Schema enforcement   │  │
    │  └──────────┬────────────┘  │
    │             │               │
    │  ┌──────────▼────────────┐  │
    │  │       SILVER          │  │
    │  │  Cleansed · typed     │  │
    │  │  CDC detection        │  │
    │  │  SCD2 logic           │  │
    │  │  Late-arriving data   │  │
    │  └──────────┬────────────┘  │
    │             │               │
    │  ┌──────────▼────────────┐  │
    │  │        GOLD           │  │
    │  │  Star schema          │  │
    │  │  Fact + Dim tables    │  │
    │  │  Query-ready          │  │
    │  └───────────────────────┘  │
    └─────────────────────────────┘
                  │
       ┌──────────┼──────────┐
       ▼          ▼          ▼
   BI Analyst   Quant    Exec Dashboard
```

### Bronze Layer — Schema in Databricks
```sql
CREATE SCHEMA IF NOT EXISTS bronze;

-- One table per source/endpoint combination
-- Example: daily price data
CREATE TABLE IF NOT EXISTS bronze.av_daily_prices
USING DELTA
LOCATION '/mnt/bronze/alpha_vantage/time_series_daily/'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.columnMapping.mode' = 'name'   -- enables schema evolution field renames
);

-- Schema enforcement constraint example
ALTER TABLE bronze.av_daily_prices
ADD CONSTRAINT valid_ticker CHECK (ticker IS NOT NULL AND LENGTH(ticker) > 0);
```

Key Bronze decisions:
- `mergeSchema = true` on all writes — absorb new fields from older/newer records without breaking
- Add `_ingest_timestamp`, `_batch_date`, `_source_file` metadata columns to every table
- Never update or delete — Bronze is append-only, immutable raw history
- Reject records that fail the constraint (null ticker, null date) — log rejections to a quarantine table

### Silver Layer — Normalized Tables
```
silver.daily_price          — one row per ticker per trading day
silver.company_profile      — company metadata (SCD2 source)
silver.financial_statement  — quarterly income + balance + cash flow, one wide row
silver.earnings_event       — EPS actual vs estimated, report date vs period end date
silver.insider_trade        — individual insider transactions, enriched with role
silver.key_metrics          — quarterly derived ratios
```

Key Silver decisions:
- Type-cast everything: `"None"` strings → NULL, date strings → DATE type
- Standardize drug names / company names to uppercase stripped form
- CDC: hash key fields on each incoming Bronze record, compare against existing Silver row — insert change record if hash differs
- Late-arriving data: always use `period_end_date` as the event date, not `ingest_date`

### Gold Layer — Star Schema
```
FACT: fact_stock_daily
  fact_sk               BIGINT (surrogate, generated)
  dim_date_sk           BIGINT FK → dim_date
  dim_company_sk        BIGINT FK → dim_company (SCD2 current key)
  open_price            DECIMAL(18,4)
  high_price            DECIMAL(18,4)
  low_price             DECIMAL(18,4)
  close_price           DECIMAL(18,4)
  adj_close_price       DECIMAL(18,4)   -- split and dividend adjusted
  volume                BIGINT
  daily_return_pct      DECIMAL(8,4)    -- derived: (close - prev_close) / prev_close

FACT: fact_earnings_event
  fact_sk               BIGINT
  dim_date_sk           BIGINT FK → dim_date  (filing date — when info became known)
  dim_company_sk        BIGINT FK → dim_company
  dim_period_sk         BIGINT FK → dim_fiscal_period
  reported_eps          DECIMAL(10,4)
  estimated_eps         DECIMAL(10,4)
  surprise_pct          DECIMAL(8,4)
  beat_flag             BOOLEAN

FACT: fact_insider_trade
  fact_sk               BIGINT
  dim_date_sk           BIGINT FK → dim_date
  dim_company_sk        BIGINT FK → dim_company
  dim_insider_sk        BIGINT FK → dim_insider (SCD2)
  transaction_type      STRING          -- Buy / Sell / Option Exercise
  shares                BIGINT
  value_usd             DECIMAL(18,2)

DIM: dim_date
  date_sk               BIGINT
  full_date             DATE
  year                  INT
  quarter               INT
  month                 INT
  month_name            STRING
  week_of_year          INT
  day_of_week           STRING
  is_trading_day        BOOLEAN         -- excludes weekends and US market holidays
  is_quarter_end        BOOLEAN

DIM: dim_company  (SCD2)
  company_sk            BIGINT          -- surrogate key (new row per change)
  ticker                STRING          -- natural key
  company_name          STRING
  sector                STRING          -- e.g. "Communication Services" (META changed in 2018)
  industry              STRING
  exchange              STRING
  market_cap_category   STRING          -- Large / Mid / Small cap (derived)
  employee_count        INT
  scd_effective_from    DATE
  scd_effective_to      DATE            -- NULL if current
  scd_is_current        BOOLEAN

DIM: dim_insider  (SCD2)
  insider_sk            BIGINT
  insider_id            STRING          -- natural key (name + company)
  full_name             STRING
  role                  STRING          -- CEO / CFO / Director etc.
  scd_effective_from    DATE
  scd_effective_to      DATE
  scd_is_current        BOOLEAN

DIM: dim_fiscal_period
  period_sk             BIGINT
  fiscal_year           INT
  fiscal_quarter        INT
  period_label          STRING          -- e.g. "FY2024 Q3"
  period_start_date     DATE
  period_end_date       DATE
```

---

## 8. The 5 Core Concepts — Implementation Map

### 1. Schema Evolution
**Where:** Bronze layer, on write  
**How:** When Alpha Vantage adds a new field (e.g. `"analyticsConfidence"` that didn't exist in 2020 records), older files and newer files have different schemas. Databricks Auto Loader with `cloudFiles.inferColumnTypes = true` and `mergeSchema = true` absorbs new columns automatically without failing the pipeline.  
**Real trigger in this dataset:** Pull AAPL data from 2004 and from 2024 in the same Bronze table — field populations differ significantly.

### 2. Schema Enforcement
**Where:** Bronze layer, on write  
**How:** Delta table constraints reject records that violate defined rules before they reach Silver.
```sql
ALTER TABLE bronze.av_daily_prices
ADD CONSTRAINT positive_close CHECK (close_price > 0);

ALTER TABLE bronze.av_daily_prices
ADD CONSTRAINT valid_date CHECK (trade_date >= '1990-01-01');
```
Rejected records go to a `bronze.quarantine` table with rejection reason logged.

### 3. Late Arriving Data
**Where:** Silver → Gold, in `fact_earnings_event`  
**How:** FMP's earnings data has two distinct dates:
- `period_end_date` — when the fiscal quarter actually ended (e.g. 2024-09-30)
- `report_date` — when the company filed the report (e.g. 2024-10-31, up to 3 months later)

A quant backtesting a strategy must only use information that was actually *available* at a given point in time. So `dim_date_sk` in `fact_earnings_event` must bind to `report_date` (when it was known), not `period_end_date`. Records arriving after initial load (amended filings) must be inserted with their true `report_date` even if that date is in the past relative to the current batch.

### 4. Change Data Capture (CDC)
**Where:** Bronze → Silver, for `company_profile` and `daily_price`  
**How:** Each time a Bronze record is processed into Silver, compute a hash of its key fields:
```python
import hashlib, json

def compute_hash(record: dict, key_fields: list) -> str:
    subset = {k: record.get(k) for k in key_fields}
    return hashlib.md5(json.dumps(subset, sort_keys=True).encode()).hexdigest()
```
Compare the incoming hash against the stored hash in Silver. If it differs → the record changed → insert a new Silver row and mark the old one as superseded. If it matches → idempotent, skip.

**Real trigger in this dataset:** Alpha Vantage `COMPANY_OVERVIEW` returns `AnalystTargetPrice` which changes weekly. Pull the same ticker on two different days and CDC will detect the change.

### 5. SCD Type 2 (Slowly Changing Dimensions)
**Where:** Silver → Gold, on `dim_company` and `dim_insider`  
**How:** When CDC detects a change in a dimension attribute, do NOT overwrite the existing Gold row. Instead:

```sql
-- Step 1: Close the current row
UPDATE gold.dim_company
SET scd_effective_to = CURRENT_DATE - 1,
    scd_is_current = FALSE
WHERE ticker = 'META'
  AND scd_is_current = TRUE;

-- Step 2: Insert the new row
INSERT INTO gold.dim_company
VALUES (next_surrogate_key, 'META', 'Meta Platforms', 
        'Communication Services', ..., CURRENT_DATE, NULL, TRUE);
```

**Real SCD2 events in this dataset:**
- META: sector changed from "Technology" to "Communication Services" (2018)
- JNJ: Kenvue spinoff changes company profile (2023)
- NVDA: post-split market cap category change (2024)
- Any insider who changes role (Director → CEO) triggers SCD2 on `dim_insider`

---

## 9. Databricks Free Edition — Constraints and Workarounds

| Constraint | Workaround |
|---|---|
| No automated pipelines / jobs scheduler | Run notebooks manually, cell by cell |
| No Auto Loader in some free tiers | Use `COPY INTO` command to load from uploaded files |
| Limited cluster uptime | Keep notebooks modular — one notebook per layer per concern |
| No Delta Live Tables | Write standard Delta SQL and PySpark instead |
| Manual file upload only | Upload JSON files from local lake to DBFS via UI |

**Recommended Databricks notebook structure:**
```
01_bronze_load.ipynb        — COPY INTO from DBFS, apply constraints
02_silver_transform.ipynb   — flatten, type-cast, CDC
03_silver_scd2.ipynb        — SCD2 merge logic for dim tables
04_gold_facts.ipynb         — build fact tables from Silver
05_gold_dims.ipynb          — build dimension tables
06_data_quality.ipynb       — row counts, null checks, SCD2 audit
```

---

## 10. Suggested Build Order

Build in this sequence — each step is testable before moving to the next:

1. **Set up folder structure** — create `fintech_datalake/` with all subfolders
2. **Write `config.py` and `utils.py`** — foundation for all scripts
3. **Ingest 1 ticker, 1 endpoint** — test Alpha Vantage `COMPANY_OVERVIEW` for `AAPL`
4. **Validate raw JSON** — inspect what actually comes back, note the `"None"` string issue
5. **Ingest all 10 tickers, all endpoints** — spread across days respecting rate limits
6. **Upload Bronze to Databricks** — create Delta tables with `COPY INTO`
7. **Add schema enforcement constraints** — test rejection of a bad record
8. **Build Silver transformations** — flatten, type-cast, one table at a time
9. **Implement CDC** — detect changes between ingestion runs
10. **Build `dim_company` with SCD2** — most complex dimension first
11. **Build `dim_date`** — pure SQL, no API needed, generate the full calendar
12. **Build `fact_stock_daily`** — join Silver price to dims
13. **Build `fact_earnings_event`** — implement late-arriving data logic here
14. **Build remaining facts and dims** — insider trades, key metrics
15. **Write data quality notebook** — row counts, null audit, SCD2 integrity check

---

## 11. Interview Talking Points

When presenting this project, frame it this way:

> *"I designed a medallion architecture for a FinTech data platform, ingesting stock market and company fundamental data from two external APIs into a Databricks Delta Lake. The pipeline handles real-world data engineering challenges including schema evolution across 20 years of records, CDC for detecting dimension changes between API pulls, SCD Type 2 on the company dimension to preserve historical sector classifications and corporate actions, and late-arriving fact handling to ensure backtesting accuracy — binding earnings data to when information was actually known, not when the fiscal period ended."*

The 5 concepts, explained plainly:
- **Schema Evolution** — old records have fewer fields than new ones. The pipeline absorbs new columns without breaking.
- **Schema Enforcement** — bad records (null tickers, negative prices) are rejected before reaching Silver. Nothing dirty reaches analysts.
- **Late Arriving Data** — an earnings report filed 6 weeks after quarter-end still gets the correct event date, not today's date.
- **CDC** — if a company's analyst target price changes between Monday's pull and Friday's pull, the pipeline detects that change and records it.
- **SCD2** — when Meta moved from the Technology sector to Communication Services, every historical row in `dim_company` still correctly says "Technology" for the period before the change. Quants backtesting 2015 data get 2015-accurate company attributes.

---

## 12. Tech Stack Summary

| Layer | Tool |
|---|---|
| Data sources | Alpha Vantage API, FMP API |
| Ingestion language | Python 3.x (`requests`, `json`, `os`, `hashlib`) |
| Local storage | Filesystem (folder-based Data Lake simulation) |
| Cloud platform | Databricks Free Edition |
| Storage format | Delta Lake (all layers) |
| Query language | SQL + PySpark |
| Dimensional model | Star Schema (fact + dimension tables) |
| Version control | Git (recommended — one repo for all scripts and notebooks) |

---

*End of handoff document. Start with Step 1 in Section 10 — build order.*

# FinTech Medallion Data Platform

A stock-market data platform built the way a small data team would build it in production, except it runs entirely on free tiers and costs nothing to operate.

It pulls daily prices, fundamentals, corporate actions, and insider filings for ten large-cap tickers, moves them through Bronze, Silver, and Gold layers across Databricks and dbt, and publishes the result to public Tableau dashboards on a weekly schedule.

Ten tickers is a small amount of data, and that is on purpose. The data is not the point. The engineering around it is: schema evolution on ingest, SCD2 history, point-in-time joins, data-quality gates, infrastructure as code, CI/CD, and one scheduled pipeline that runs the whole chain end to end. Every non-trivial decision is written down as an [ADR](docs/adr/), so the repo explains *why* each piece looks the way it does, not just what it does.

## What it does

- Reads from three sources. Financial Modeling Prep is the primary feed for prices, fundamentals, and corporate actions. Alpha Vantage supplies a second price series used only to cross-check FMP. SEC EDGAR provides Form 4 insider transactions, parsed from XML into normalized JSON at ingest time.
- Lands raw JSON in a local lake, then loads it into Databricks as append-only Bronze Delta tables using Autoloader, with rescue-mode schema evolution so an unexpected field never breaks a load.
- Cleanses and historizes in Silver with Delta Live Tables: an SCD2 company dimension, deduplicated event tables, and a separate data-quality schema that reconciles the two price feeds and audits coverage.
- Builds a Kimball star schema in Gold with dbt: three dimensions, seven facts, two aggregates, surrogate keys, and a point-in-time join that attaches each fact to the version of the company that was current on the event date.
- Serves Gold to Tableau Public through a Google Sheets reverse-ETL step, because Tableau Public has no Databricks connector on the free tier.

## Architecture

```
Python ingest  ->  Local JSON lake  ->  Databricks Free Edition  ->  dbt Cloud  ->  Google Sheet  ->  Tableau Public
                                         Bronze + Silver              Gold marts     serving layer    dashboards
```

An interactive, animated version of this flow is published as the project's [architecture map](https://pangamu1.github.io/fintech-medallion-portfolio/).

Each layer has a single owner, and the boundaries are deliberate rather than incidental:

| Layer | Owner | Responsibility |
|---|---|---|
| Ingestion | Python (`fintech_datalake/scripts/`) | Call the APIs, write atomic JSON to the local lake, log every run |
| Bronze | Databricks Autoloader + Delta | Raw, append-only, schema evolution via `cloudFiles` rescue mode |
| Silver | Databricks Delta Live Tables | Cleansing, CDC, SCD2 history, late-arriving fixes, quality expectations |
| Gold | dbt Cloud | Star schema, tests, lineage docs |

One rule that drives a lot of the design: Silver owns CDC and SCD2, not dbt. dbt consumes the already-historized Silver tables and surfaces them as Gold dimensions with surrogate keys. The reasoning is in [ADR-0002](docs/adr/0002-medallion-layer-ownership.md).

The data-ecosystem diagram is in [`fintech_data_ecosystem.svg`](fintech_data_ecosystem.svg).

## Stack

Everything here is a free tier. Where a free tier fell short, the workaround is documented in an ADR rather than papered over.

| Tool | Role | Why this one |
|---|---|---|
| `uv` | Python dependencies and venv | Fast, reproducible, lockfile committed |
| Databricks Free Edition | Bronze + Silver compute (Autoloader, DLT) | Serverless, no cluster to manage, DLT included |
| dbt Cloud Developer | Gold transformations | Managed runs, hosted docs, generous monthly run budget |
| HCP Terraform | Infrastructure as code | Free remote state, plans the Databricks and GitHub resources |
| GitHub Actions | CI/CD and orchestration | Serverless cron and runners, unlimited minutes on public repos |
| GitHub Pages | Hosts the architecture map and dbt lineage docs | Static hosting that comes with the repo |
| Tableau Public | Dashboards | The free Tableau tier, fed through Google Sheets |

The free tiers are not without teeth. Databricks Free Edition runs roughly one serverless workload at a time, Alpha Vantage allows 25 calls a day, FMP caps four of its fundamentals endpoints at five records per call, and Tableau Public cannot connect to a warehouse directly. Each of those constraints shaped a decision you can read about in the [decision log](docs/adr/).

## Orchestration

The full chain runs as a single scheduled GitHub Actions workflow, [`master-pipeline.yml`](.github/workflows/master-pipeline.yml). It fires every Monday at 06:00 UTC, and chains `ingest -> bronze -> silver -> gold -> serve` through job dependencies so that a failure in any stage halts everything downstream instead of publishing half a run. The fan-out stages run one job at a time, because Databricks Free Edition will not run them in parallel.

GitHub Actions was a deliberate choice over Airflow. Actions is serverless, so GitHub hosts the schedule and the runners and there is nothing always-on to pay for or babysit. Airflow's scheduler is a daemon that has to run continuously whether or not a pipeline is firing, which does not fit a no-ops, free-tier project. The full reasoning is in [ADR-0026](docs/adr/0026-unified-gha-orchestrator.md).

A second pair of workflows, [`ci.yml`](.github/workflows/ci.yml) and [`prod.yml`](.github/workflows/prod.yml), handles the dbt development loop: pull requests run a slim build, and merges to `main` trigger the production build and refresh the lineage docs.

## Repository layout

```
fintech_datalake/        Python ingestion and the local JSON lake
  scripts/               ingest_*.py, upload_bronze_to_uc.py, serve_to_sheets.py, config.py, utils.py
  bronze/ silver/ gold/  local lake directories (kept in git, contents ignored)
databricks/
  jobs/bronze_autoloader/   Bronze Autoloader entry point
  dlt/silver/               seven Delta Live Tables pipelines
fintech_dbt/             Gold layer (dbt project, has its own README)
terraform/               infrastructure: Unity Catalog, jobs, pipelines, GitHub secrets and vars
.github/workflows/       ci.yml, prod.yml, master-pipeline.yml, bi-refresh.yml
docs/adr/                architecture decision records
```

## Running it

This is a portfolio project, not a package, so reproducing it end to end means bringing your own accounts: Databricks, dbt Cloud, FMP and Alpha Vantage keys, a Google service account, and an HCP Terraform workspace. The ingestion layer, though, runs on its own with just two API keys.

```bash
# install dependencies (uv reads pyproject.toml + uv.lock)
uv sync

# set your keys
cp .env.example .env   # then fill in FMP_API_KEY and ALPHA_VANTAGE_API_KEY

# pull the sources into the local lake
cd fintech_datalake/scripts
uv run python ingest_fmp.py
uv run python ingest_alpha_vantage.py
uv run python ingest_sec_edgar.py
```

The Databricks, dbt, and serving layers are provisioned with Terraform and run by the orchestrator. The dbt layer has its own setup notes in [`fintech_dbt/README.md`](fintech_dbt/README.md).

## Decisions

The [`docs/adr/`](docs/adr/) directory is the heart of the repo. It holds the architecture decision records in [MADR](https://adr.github.io/madr/) format, written as the project went along. Reversals are handled by writing a new record that supersedes the old one, never by editing history, so the log doubles as a timeline of how the design actually evolved (including the wrong turns).

## Live

- Tableau dashboards: https://public.tableau.com/app/profile/piruthviraj.a.s/viz/FinTechMedallion-MarketAnalytics/ExecutiveOverview
- Architecture map: https://pangamu1.github.io/fintech-medallion-portfolio/
- dbt lineage docs: https://pangamu1.github.io/fintech-medallion-portfolio/dbt-docs/

## A note on scope

The dashboards refresh weekly, not in real time, and the ticker universe is fixed at ten names chosen to exercise specific edge cases: a dual-class structure, a sector reclassification, a spinoff, a stock split, and a company that pays no dividend. The goal was to hit the interesting engineering problems a real platform runs into, at a scale that stays free to run.

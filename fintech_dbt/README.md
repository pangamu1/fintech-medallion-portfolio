# Gold layer (dbt)

This is the Gold layer of the [FinTech Medallion platform](../README.md). It is a dbt Cloud project that turns the historized Silver tables in Databricks into a Kimball star schema that the dashboards read from.

It does not do any change-data-capture or SCD2 work. That happens upstream in the Silver Delta Live Tables. By the time data reaches here it is already cleansed and historized, so dbt's job is narrow: assign surrogate keys, join facts to the correct point-in-time dimension version, apply tests, and publish marts with lineage docs. The split is deliberate and is argued in [ADR-0002](../docs/adr/0002-medallion-layer-ownership.md).

## Where it sits

```
silver.* (Databricks Unity Catalog)  ->  dbt models  ->  gold.marts
```

Sources are declared in [`models/sources/silver_sources.yml`](models/sources/silver_sources.yml) against the `silver` schema. The production build writes to `gold.marts`; pull-request builds write to a developer schema so they never touch production.

## The models

Twelve models, grouped by the two things a star schema needs.

**Dimensions** (`models/marts/core/`, materialized as tables)

| Model | Notes |
|---|---|
| `dim_date` | Calendar from 1960 to 2030, with NYSE trading-day and holiday flags driven by the `nyse_holidays` seed |
| `dim_company` | SCD2 company dimension. Surrogate key is `generate_surrogate_key(['symbol', '__START_AT'])`; the first version of each company is backdated to 1900-01-01 so early facts always find a match |
| `dim_fiscal_period` | Fiscal-period dimension for the statement and metric facts |

**Facts and aggregates** (`models/marts/finance/`)

| Model | Materialization | Grain |
|---|---|---|
| `fact_stock_daily` | incremental (merge) | one row per symbol per trading day |
| `fact_earnings_event` | incremental (merge) | one row per earnings announcement |
| `fact_financial_statement` | incremental (merge) | one row per statement line item |
| `fact_key_metric` | incremental (merge) | one row per metric per period |
| `fact_dividend_event` | incremental (merge) | one row per dividend |
| `fact_split_event` | incremental (merge) | one row per split |
| `fact_insider_trade` | incremental (merge) | one row per Form 4 transaction line |
| `agg_sector_daily` | table | sector rollup per trading day |
| `agg_company_monthly` | table | one row per symbol per month |

The facts use an incremental merge with a short lookback window rather than a full rebuild, so a scheduled run only reprocesses recent partitions. `fact_stock_daily`, for example, re-merges the last seven days on each incremental run.

## Conventions

- **Surrogate keys** come from `dbt_utils.generate_surrogate_key` over the natural key plus the SCD2 effective-from column, so each historical version of a company gets its own key.
- **Point-in-time joins** go through the [`pit_join_company`](macros/pit_join_company.sql) macro. It attaches the `dim_company` version that was current on the fact's event date, using a half-open interval `[scd_effective_from, scd_effective_to)` with the open-ended current row handled by a coalesce to 9999-12-31. This is what keeps a trade or a price attributed to the company as it was on that day, not as it is now.
- **Dimensions and aggregates are tables; facts are incremental.** The defaults live in [`dbt_project.yml`](dbt_project.yml); facts override to `incremental` in their own files.
- Packages are pinned in [`packages.yml`](packages.yml): `dbt_utils` for surrogate keys and tests, `dbt_date` for the calendar.

## Running it

The project runs on dbt Cloud (Developer plan), and the day-to-day loop is driven by GitHub Actions rather than a local install.

- **On a pull request**, [`ci.yml`](../.github/workflows/ci.yml) runs `dbt build --select state:modified+` through the dbt Cloud CLI. It defers to the production state automatically and builds only what changed, into a developer schema.
- **On merge to `main`**, [`prod.yml`](../.github/workflows/prod.yml) triggers the dbt Cloud production job through the Admin API, polls it to completion, and refreshes the lineage docs.

If you want to run it yourself, you need a dbt Cloud project pointed at a Databricks warehouse with the Silver tables in place, then:

```bash
dbt deps          # install dbt_utils and dbt_date
dbt build         # run models, tests, and seeds
```

The CI and CD design, including why the production build has to go through a Cloud job rather than the CLI, is written up in [ADR-0022](../docs/adr/0022-cicd-github-actions-dbt-cloud.md).

## Lineage docs

dbt generates a browsable lineage and documentation site. It is published as part of the platform's GitHub Pages site, on a subpath:

https://pangamu1.github.io/fintech-medallion-portfolio/dbt-docs/

The production job regenerates it on every merge to `main`, so the hosted version tracks `main`. To build and read it locally instead:

```bash
dbt docs generate
dbt docs serve     # opens the docs at http://localhost:8080
```

## Layout

```
models/
  sources/        silver_sources.yml   declares the Silver source tables
  marts/core/     the three dimensions
  marts/finance/  the seven facts and two aggregates
macros/           pit_join_company.sql
seeds/            nyse_holidays.csv
```

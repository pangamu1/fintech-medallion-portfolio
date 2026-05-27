# 0002 — Medallion layer ownership: Python / Databricks / DBT

- **Status:** Accepted. Bronze row partially superseded by [ADR-0018](0018-bronze-pyspark-autoloader-supersedes-copy-into.md) (2026-05-26) — Bronze engine changed from `COPY INTO` + Delta to PySpark Autoloader + Delta. Silver (DLT) and Gold (dbt) ownership rows unchanged.
- **Date:** 2026-05-22
- **Deciders:** project owner

## Context

The medallion architecture (Bronze / Silver / Gold) leaves open *which tool owns which layer*. The handoff doc this project was scaffolded against had stale guidance ("no DLT on Free Edition"), and we needed to settle ownership before writing ingestion code that would otherwise overlap with Silver responsibilities. CDC and SCD2 in particular have two natural homes — they could live in Silver (Databricks DLT) or in Gold (dbt snapshots). Putting them in both, or in the wrong place, would produce duplicate history tracking and undermine the lineage story.

Free Edition constraints in play: Databricks Serverless SQL Warehouse + Delta Live Tables verified available 2026-05-15; dbt Cloud Developer plan supports ~3,000 model runs/month; Python ingestion runs locally (no cloud cost).

## Decision

| Layer | Owner | Logic |
|---|---|---|
| Ingestion | Python scripts in `fintech_datalake/scripts/` | Hit Alpha Vantage + FMP, land raw JSON in local Bronze lake |
| Bronze | Databricks (`COPY INTO` + Delta) | Raw, append-only, schema evolution + enforcement |
| Silver | Databricks DLT pipelines | Cleansing, CDC, SCD2 history tables, late-arriving fix, DLT Expectations for data quality |
| Gold | DBT Cloud (Developer plan) | Star schema dims + facts, tests, lineage docs |

**Silver owns CDC and SCD2.** DBT consumes the already-historized Silver SCD2 tables and surfaces them as Gold dimensions with surrogate keys via `dbt_utils.generate_surrogate_key`. DBT does not run `dbt snapshot`.

## Considered alternatives

- **DBT owns SCD2 via `dbt snapshot`** — rejected. DLT's `create_auto_cdc_flow(..., stored_as_scd_type=2)` is native and runs server-side; running snapshots from dbt Cloud would burn model-run budget on slowly-changing data that barely changes. Also splits CDC across two tools, hurting lineage clarity.
- **Vanilla PySpark notebooks for Silver instead of DLT** — rejected. The handoff doc claimed DLT wasn't on Free Edition; that turned out to be stale (verified 2026-05-15 with a working `DLT_Bookings_Silver` pipeline). DLT gives us declarative expectations and managed CDC for free; no reason to hand-roll `MERGE INTO` statements.
- **Push ingestion into Databricks (Auto Loader + cloud storage)** — rejected for portfolio reasons. Running Python locally lets reviewers see and reproduce the ingestion code without needing Databricks credentials. The local-Bronze step is then mirrored to a Unity Catalog Volume before `COPY INTO`.

## Consequences

- **Positive:** Single owner per layer; no overlapping CDC logic. DLT's expectations show up in the pipeline event log, giving us free data-quality observability. dbt Cloud stays under its 3k-runs/month budget because Gold runs only on Silver-table changes.
- **Negative / cost:** Reviewers need familiarity with two execution environments (Databricks notebooks/DLT and dbt Cloud) to read the pipeline end-to-end. The Python→Databricks Volume upload step adds an extra orchestration hop.
- **Follow-ups required:** `feat/bronze-databricks` to wire `COPY INTO` Bronze. `feat/silver-dlt` to implement DLT pipelines. `feat/gold-dbt` for the Gold star schema.

## References

- Databricks Delta Live Tables docs — https://docs.databricks.com/delta-live-tables/index.html
- `dlt.create_auto_cdc_flow` API — https://docs.databricks.com/delta-live-tables/python-ref.html
- Kimball star-schema methodology — *The Data Warehouse Toolkit*, 3rd ed.

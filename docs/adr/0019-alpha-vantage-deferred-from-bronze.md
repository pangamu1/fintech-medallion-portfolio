# 0019 — Alpha Vantage `TIME_SERIES_DAILY` deferred from Bronze; Silver consumes JSON directly

- **Status:** Accepted
- **Date:** 2026-05-27
- **Deciders:** project owner
- **Amends:** the cardinality row of [ADR-0018](0018-bronze-pyspark-autoloader-supersedes-copy-into.md). Bronze stream cardinality drops from 11 streams to **10 (FMP only)**. ADR-0018's Bronze design otherwise stands.
- **Builds on:** [ADR-0009](0009-alpha-vantage-downgrade-fmp-primary-prices.md) (AV downgraded to cross-validation only).

## Context

ADR-0018 specified one Autoloader stream per `(source, endpoint)` — 11 streams total: 1 Alpha Vantage (`time_series_daily`) plus 10 FMP. The Bronze transformation pattern is `explode(col("data"))`, which assumes `data` is an `ARRAY` of records.

CP9 surfaced that this assumption holds for **FMP only**. Alpha Vantage's `TIME_SERIES_DAILY` response shape is fundamentally incompatible:

```json
{
  "_source": "alpha_vantage",
  "_endpoint": "time_series_daily",
  "data": {
    "Meta Data": { "1. Information": "...", "2. Symbol": "AAPL", ... },
    "Time Series (Daily)": {
      "2026-05-20": { "1. open": "...", "2. high": "...", ... },
      "2026-05-19": { ... },
      ...
    }
  }
}
```

`data` is a `STRUCT`, not an `ARRAY`. Each trading date is encoded as a **field name** in the `Time Series (Daily)` nested struct, with the OHLCV record as its value. The `bronze_autoloader_alpha_vantage_time_series_daily` job fails at analysis time with:

> `[DATATYPE_MISMATCH.UNEXPECTED_INPUT_TYPE] Cannot resolve "explode(data)" due to data type mismatch: The first parameter requires the ("ARRAY" or "MAP") type, however "data" has the type "STRUCT<…>"`

Rescue mode does not save us either. `cloudFiles.schemaEvolutionMode = "rescue"` freezes the schema at first inference; AV's dates-as-fields shape means the schema would lock to "the trading days present in the first file processed," and every subsequent day's data would either bloat the schema (with `addNewColumns`) or be quarantined to `_rescued_data` (with `rescue`). Neither produces a queryable daily-price table going forward.

This isn't a fixable bug. It's a design mismatch between ADR-0018's Bronze pattern and the AV payload shape.

## Decision

Alpha Vantage is **removed from Bronze.** The `alpha_vantage.time_series_daily` entry is deleted from `terraform/bronze_jobs.tf`'s `locals.bronze_jobs` map. No `bronze.alpha_vantage.time_series_daily` Delta table is created or maintained.

What stays:

| Artifact | Retained because |
|---|---|
| `databricks_catalog.bronze` | Used by 10 FMP tables. |
| `databricks_schema.bronze_alpha_vantage` | Empty container; cheap to keep; available if future AV endpoints ever fit the Bronze pattern. |
| `databricks_catalog.ingestion` + `databricks_schema.ingestion_alpha_vantage` + `databricks_volume.ingestion_alpha_vantage_raw_jsons` | AV JSON files continue to land here via `upload_bronze_to_uc.py`. Silver reads them directly. |
| `fintech_datalake/scripts/ingest_alpha_vantage.py` | Daily AV ingestion continues unchanged. |
| `fintech_datalake/scripts/upload_bronze_to_uc.py` | Endpoint-agnostic; uploads AV alongside FMP. No changes required. |

Silver-layer consumption pattern (per [ADR-0009](0009-alpha-vantage-downgrade-fmp-primary-prices.md)): when implementing FMP↔AV cross-validation, Silver code reads AV directly:

```python
av_df = (spark.read
         .option("multiLine", "true")
         .json("/Volumes/ingestion/alpha_vantage/raw_jsons/time_series_daily/"))
# Silver-specific transformation pivots the date-keyed struct into rows.
```

The pivot logic — converting the date-keyed struct into one row per `(ticker, date)` — lives in Silver because:
1. AV's role is cross-validation, not a primary feed. The transformation is a Silver-internal preparation step, not a Bronze layer in its own right.
2. The pivot requires either `to_json` + re-parse with explicit `MapType`, or a Spark Connect-friendly `stack()` over a small number of statically-named fields. Both fit Silver's transformation surface; neither belongs in the uniform Bronze Autoloader pattern.

## Considered alternatives

- **A. Per-source dispatch in `databricks/jobs/bronze_autoloader/run.py`** — branch on `source == "alpha_vantage"` and implement an AV-specific transformation (parse `data.\`Time Series (Daily)\`` as a map, explode entries, flatten the OHLCV struct with field-name escaping for `1. open` etc.). **Rejected.** Half-day's work for a feed already scoped to cross-validation; bloats `run.py` with per-source branching that would expand with every new source whose shape doesn't fit; Spark Connect struct→map conversion is awkward enough to be its own micro-design problem. Silver is a more natural home for that complexity.
- **B. Pre-process AV JSON at upload time** — transform the AV response in `upload_bronze_to_uc.py` (pluck `Time Series (Daily)`, emit a normalized array shape, upload the transformed payload). **Rejected.** Violates [ADR-0007](0007-bronze-ingestion-durability-atomic-writes-jsonl-logs.md) ("Bronze is the raw landing zone"); the on-disk AV JSON would no longer reflect what the API returned; loses provenance. Pre-Bronze transformation is the worst place for shape-normalization logic.
- **C. Land AV in Bronze using Path A row granularity (one row per file, `data` kept as nested struct)** — Bronze schema would lock to the first file's date set, with `_rescued_data` capturing every new day. **Rejected** for the same reason rescue mode doesn't save the explode pattern: the schema decays into garbage over time.
- **D. Drop AV entirely; rely on FMP alone** — already considered and rejected in [ADR-0009](0009-alpha-vantage-downgrade-fmp-primary-prices.md). Cross-validation is a strict portfolio-narrative upgrade over single-source ingestion.

## Consequences

- **Positive:**
  - CP9 unblocked. 10 FMP jobs run cleanly; AV deferred without blocking forward progress.
  - Silver gets exactly one place to own the AV shape-pivot, colocated with the FMP↔AV reconciliation it feeds.
  - Bronze stays simple: one transformation pattern (`explode(data)`), uniformly applied. No per-source branching in `run.py`.
  - Local lake → UC volume upload path is unchanged. The producer side stays uniform across both sources.
- **Negative / cost:**
  - **Asymmetric Bronze layer.** 10 of 11 endpoints are queryable as `bronze.fmp.*` Delta tables; AV is not queryable in Bronze at all. A reader scanning UC catalogs would not see AV anywhere obvious in `bronze.*`.
  - **Silver carries a second reader pattern.** FMP comes from `bronze.fmp.*` (Delta tables, SQL-friendly); AV comes from `/Volumes/ingestion/alpha_vantage/raw_jsons/` (JSON via `spark.read.json`). Two read paths to learn.
  - **The `bronze.alpha_vantage` schema is empty.** Either it stays as an aspirational container (kept under TF, no tables inside), or it becomes a follow-up cleanup if no AV endpoints ever fit the Bronze pattern. Cost is near-zero; flag for cleanup at portfolio polish time.
  - "Bronze handles all source ingestion uniformly" is no longer a true claim. The narrative becomes "Bronze handles array-shaped JSON sources uniformly; struct-keyed shapes are handled at Silver." More nuanced; defensible at interview.
- **Follow-ups required:**
  - Plan file `~/.claude/plans/feat-bronze-databricks.md` — note CP9.b's AV failure + this resolution.
  - `CLAUDE.md` — no immediate change. The Layer-ownership table's Bronze row still describes the *engine* correctly; the cardinality detail (10 vs 11) is plan-file-level.
  - Silver branch (`feat/silver-dlt`) — implement AV reader + pivot (struct-of-dates → rows of `(ticker, date, open, high, low, close, volume)`); implement FMP↔AV cross-validation as `@dlt.expect_or_log` per [ADR-0009](0009-alpha-vantage-downgrade-fmp-primary-prices.md).
  - Open question to revisit at Silver time: if AV ever gains additional endpoints with array-shaped responses (e.g., `OVERVIEW`), those *could* re-enter the Bronze pattern. Decide at that point whether to add them back to `locals.bronze_jobs` or keep all AV ingestion at Silver for consistency.

## References

- [ADR-0009](0009-alpha-vantage-downgrade-fmp-primary-prices.md) — AV downgraded to cross-validation; this ADR is the operational follow-through.
- [ADR-0018](0018-bronze-pyspark-autoloader-supersedes-copy-into.md) — Bronze Autoloader pattern this ADR amends the scope of.
- [ADR-0007](0007-bronze-ingestion-durability-atomic-writes-jsonl-logs.md) — "Bronze is raw" principle that Alternative B would have violated.
- AV `TIME_SERIES_DAILY` response shape — observed during CP9.b.2 on 2026-05-27.
- Plan file `~/.claude/plans/feat-bronze-databricks.md` — CP9 pause block records the failure + resolution sequence.

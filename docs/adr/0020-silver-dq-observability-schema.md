# 0020 — `silver.dq` observability schema for cross-source data-quality tables

- **Status:** Accepted
- **Date:** 2026-05-30
- **Deciders:** project owner
- **Builds on:** [ADR-0009](0009-alpha-vantage-downgrade-fmp-primary-prices.md) (Alpha Vantage downgraded to cross-validation only) and [ADR-0002](0002-medallion-layer-ownership.md) (Silver = Databricks DLT).

## Context

CP9 of `feat/silver-dlt` implements the FMP↔Alpha Vantage daily-price reconciliation promised since [ADR-0009](0009-alpha-vantage-downgrade-fmp-primary-prices.md): AV's role is cross-validation of FMP's primary price feed, not an independent source. By CP8 both inputs exist as cleansed Silver tables — `silver.fmp.daily_prices` (12540 rows, 2021→2026) and `silver.alpha_vantage.daily_prices` (1002 rows, ~100-day compact window) — so the reconciliation is now a pure Silver-on-Silver join.

The question this ADR settles is **where the reconciliation output lives**, and the new structural concept it introduces.

The Silver schemas to date are **source-aligned**: `silver.fmp.*` holds everything derived from FMP Bronze, `silver.alpha_vantage.*` holds the pivoted AV feed. A cross-validation table joins *both* sources and is owned by *neither*. Dropping it into `silver.fmp` would falsely imply it's an FMP-derived artifact; dropping it into `silver.alpha_vantage` would imply the reverse. Neither placement is honest about what the table is: an **observability / data-quality artifact** that sits above the source feeds and audits agreement between them.

This crosses the line drawn in the CP1 decisions table ("promote to ADR only on architectural change"). Introducing a new schema whose organizing principle is *concern* (observability) rather than *source* is a new layer concept in the medallion design, and it is the intended home for future DQ tables (CP11 `_file_audit` for 0-event detection; freshness/gap checks). That warrants an ADR rather than a plan-file footnote.

## Decision

We introduce a dedicated **`silver.dq`** schema for cross-source and cross-cutting data-quality / observability tables, and land the price reconciliation there as `silver.dq.price_cross_validation`.

- `silver.dq` is created as a `databricks_schema` under the existing `silver` UC catalog (mirrors `silver.fmp` and `silver.alpha_vantage` in `terraform/schemas.tf`).
- A dedicated **5th DLT pipeline `silver_dq`** (`schema="dq"`, serverless, triggered) owns the schema. Per-table schema override inside an existing pipeline is not used — a DLT pipeline writes one default schema, and the per-pipeline-per-schema pattern was already proven at CP8 when AV got its own pipeline rather than a schema override inside `silver_prices`.
- `silver.dq.price_cross_validation` inner-joins the two Silver price tables on `(symbol, price_date)`, both read via `spark.read.table` (symmetric batch reads), and computes `fmp_close`, `av_close`, `abs_diff`, `pct_diff`, and a stored `is_divergent` boolean flagging `pct_diff > 0.005` (0.5%). The threshold is a module constant `_DIVERGENCE_THRESHOLD`.
- The table carries only `@dlt.expect_or_fail("valid_key", ...)`. **No drop expectation** — an audit table must retain divergent rows by definition; dropping them would defeat its purpose. No rescue expectation — both inputs are already-cleansed Silver, no `_rescued_data` exists.

Per [ADR-0009](0009-alpha-vantage-downgrade-fmp-primary-prices.md), this table is an audit artifact only. It is **not** a Gold (DBT) input; Gold consumes FMP as the primary price source.

## Considered alternatives

- **A. Put it in `silver.fmp.price_cross_validation`** — keeps pipeline count at 4. **Rejected.** Mislabels a two-source reconciliation as an FMP-derived table; source-aligned schemas stop meaning what they say. The first reader to `SHOW TABLES IN silver.fmp` would have to know that one of these tables isn't actually "from FMP".
- **B. Put it in `silver.alpha_vantage.*`** — symmetric to A. **Rejected** for the same reason, and worse: AV is the *secondary* feed, so housing the reconciliation there over-weights the audited party.
- **C. Per-table schema override inside the existing `silver_prices` pipeline** (qualify the `@dlt.table` name with a `dq` schema). **Rejected.** CP8 already established that Free-Edition serverless DLT does not reliably support per-table schema override; AV was split into its own pipeline for exactly this reason. Re-litigating it here would risk an apply-time surprise for no benefit.
- **D. No new schema — emit reconciliation only as a DLT expectation / event-log metric** (`@dlt.expect` on a divergence condition, read divergence from the pipeline event log). **Rejected.** The event log is ephemeral observability, not a queryable table; BI/analysts cannot join to it, and per-`(symbol, date)` divergence history would be lost on log rotation. A materialized audit table is the durable artifact.

## Consequences

- **Positive:**
  - Source-aligned schemas (`silver.fmp`, `silver.alpha_vantage`) stay honest — each contains only what its name claims.
  - `silver.dq` gives the project a named observability layer with a clear charter: cross-cutting DQ that belongs to no single source. CP11 `_file_audit` (0-event-file detection) and any future freshness/gap checks now have an obvious home.
  - The reconciliation is a durable, queryable, per-`(symbol, date)` table — analysts can slice divergence by symbol or window, not just read a pass/fail metric.
  - Matches the established per-pipeline-per-schema pattern; no new infrastructure idiom to learn.
- **Negative / cost:**
  - **A 5th DLT pipeline.** More serverless cold-starts to trigger, one more TF resource set, one more observability surface. Cost is near-zero on Free Edition but the operational surface grows linearly.
  - **`silver.dq` starts with a single table.** Until CP11 lands `_file_audit`, the schema houses exactly one table — arguably premature structure. Justified by the locked roadmap (CP11 + freshness checks) and by the honesty argument above.
  - **Inner join clips to the AV window.** Reconciliation only covers the ~100-day overlap where AV has data; the 2021→2024 FMP history has no AV counterpart and is silently absent from the audit. This is inherent to AV's compact-only free tier ([ADR-0009](0009-alpha-vantage-downgrade-fmp-primary-prices.md)), not a defect of this design.
- **Follow-ups required:**
  - `CLAUDE.md` — add ADR-0020 to the Decision Log index.
  - Plan file `~/.claude/plans/feat-silver-dlt.md` — record CP9 completion + live divergence stats.
  - Memory `project_databricks_connection.md` — add `silver.dq.price_cross_validation` + the `silver_dq` pipeline to the inventory.
  - CP11 (`_file_audit`) and any freshness/gap checks land in `silver.dq` when implemented.

## Amendments

### 2026-05-30 — CP11 second `silver.dq` tenant: `coverage_audit` (reframed from `_file_audit`)

The original roadmap (ADR-0018 Consequences; `feat/silver-dlt` plan CP11) named a `_file_audit` table to **detect 0-event files** — files that landed but produced zero Bronze rows. CP11 grounding invalidated that premise:

- [`fintech_datalake/scripts/ingest_fmp.py`](../../fintech_datalake/scripts/ingest_fmp.py) (empty-list branch) **logs and skips** — an empty FMP response (`[]`) is never written to the lake, so no file is uploaded for that `(symbol, endpoint)`.
- Bronze's `explode(data)` would drop an empty array anyway.

Therefore **no 0-event files exist**: every file that reached Bronze produced ≥1 row. The phenomenon the audit was meant to catch manifests instead as **missing `(symbol, endpoint)` coverage** — a combination that never produced a file. On-disk confirmation: `dividends` absent for AMZN/TSLA (non-payers); `splits` absent for META/PYPL.

The table materialized as **`silver.dq.coverage_audit`**, a coverage matrix: `crossJoin` of the data-driven symbol universe (`DISTINCT _ticker FROM bronze.fmp.profile`) × the 10 FMP endpoints, left-joined to actual per-`(symbol, endpoint)` Bronze row counts, with `record_count` (coalesced to 0) and a `has_data` boolean. `has_data = false` flags an absent combination — expected for the four known non-payer/non-split cases, or a real ingestion gap otherwise. Only `expect_or_fail("valid_key")`; no drop (audit retains gap rows).

Implementation notes:
- Lands as a **second `@dlt.table` in the existing `silver_dq.py`** / `silver_dq` pipeline — no new pipeline or schema. This is the first concrete proof of ADR-0020's "`silver.dq` is the home for future DQ tables" claim. TF surface change was a single `databricks_workspace_file` content re-sync (`0 add, 1 change`).
- `_ticker` (envelope field, present in every Bronze table) is the uniform join key, not `record.symbol`.
- Decision (CP11): name it `coverage_audit`, not `file_audit` — the honest name for what it detects. The ADR-0018 `_file_audit` reference is superseded by this entry.

The CP11 stretch is therefore **complete within Silver**, not deferred to a separate `feat/bronze-audit` branch as the plan tentatively suggested — the coverage-matrix framing fits Silver's read-from-Bronze surface cleanly.

## References

- [ADR-0009](0009-alpha-vantage-downgrade-fmp-primary-prices.md) — AV downgraded to cross-validation; this ADR is the operational follow-through for the reconciliation it promised.
- [ADR-0019](0019-alpha-vantage-deferred-from-bronze.md) — AV-at-Silver consumption pattern that produced `silver.alpha_vantage.daily_prices`, one of the two inputs here.
- [ADR-0002](0002-medallion-layer-ownership.md) — Silver = Databricks DLT; this ADR adds the observability-schema concept within that ownership.
- Plan file `~/.claude/plans/feat-silver-dlt.md` — CP9 design locked 2026-05-30; CP9 sub-steps.
- `databricks/dlt/silver/silver_dq.py`, `terraform/silver_pipelines.tf`, `terraform/schemas.tf` — the implementation this ADR documents.

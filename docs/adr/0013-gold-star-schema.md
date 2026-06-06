# 0013 — Gold layer is a Kimball star schema: 7 facts + 3 dims + 2 aggregates

> **2026-06-06:** amended 6→7 facts (`fact_insider_trade` added) — see [Amendments](#amendments). The body below preserves the original 6-fact decision as written.

- **Status:** Accepted
- **Date:** 2026-05-22 (decision dated 2026-05-19)
- **Deciders:** project owner

## Context

The Gold layer's job is to serve BI tools (target: Tableau Public), quant consumers, and exec dashboards. The shape that those consumers expect — and that dbt is designed around — is the Kimball star schema: narrow, conformed dimensions joined to wide fact tables on surrogate keys. Anything else (snowflake, data vault, OBT) either fights the BI tool's query optimizer or adds modelling overhead that doesn't pay back at this scale.

Beyond "use a star schema," the Gold schema needs concrete definition: which facts, which dimensions, how SCD2 history surfaces, what's pre-aggregated. The decision is upstream of any dbt model code — we want to know what we're building before writing it.

## Decision

Gold consists of **11 tables**:

**6 fact tables**
- `fact_stock_daily` — daily OHLCV + adjusted close, one row per (ticker, trade_date)
- `fact_earnings_event` — earnings announcements, one row per (ticker, fiscal_period)
- `fact_financial_statement` — income / balance / cash-flow line items unioned, one row per (ticker, fiscal_period, statement_type, line_item)
- `fact_key_metric` — pre-computed ratios and metrics (P/E, ROE, etc.), one row per (ticker, fiscal_period)
- `fact_dividend_event` — dividend declarations + payments, one row per (ticker, ex_date)
- `fact_split_event` — stock splits, one row per (ticker, split_date)

**3 dimensions**
- `dim_date` — calendar dim with fiscal-quarter mapping, market-open flag, holiday flag
- `dim_company` — SCD2 (consumed from Silver, surrogate-keyed in Gold via `dbt_utils.generate_surrogate_key(['ticker', 'scd_effective_from'])`)
- `dim_fiscal_period` — fiscal-period dim distinct from calendar `dim_date` (companies have different fiscal year-ends)

**2 aggregates**
- `agg_sector_daily` — sector-level OHLCV roll-ups for the "sector heatmap" dashboard archetype
- `agg_company_monthly` — monthly OHLCV + key-metric roll-ups to keep the most-queried Tableau views off the underlying facts

`fact_insider_trade` is deliberately absent — see [ADR-0012](0012-insider-trades-phase-3-sec-edgar.md).

Facts join to `dim_company` via a `pit_join_company` macro that does point-in-time correctness: `event_date BETWEEN scd_effective_from AND COALESCE(scd_effective_to, DATE '9999-12-31')`.

## Considered alternatives

- **Snowflake schema (normalize dimensions further)** — rejected. BI tools deoptimize joins to snowflaked dims, and the marginal storage savings don't matter at our row counts.
- **Data Vault 2.0** — rejected. The hub/link/satellite triad is excellent for big-org multi-source integration; for a 2-source, 10-ticker portfolio project it's overkill and obscures the dimensional story reviewers expect.
- **One Big Table (OBT) / fully denormalized** — rejected. Loses SCD2 history shape; breaks the BI tool's query-builder; and SCD2 changes would require a Gold-wide rewrite per `dim_company` event.
- **Wider star (split `fact_financial_statement` into separate `fact_income`, `fact_balance`, `fact_cashflow`)** — considered; rejected. The line-item union model is more flexible for ad-hoc dashboarding and aligns with how FMP's free-tier responses are shaped (5 records per call across all three statements).
- **Skip aggregates; let BI tool aggregate on the fly** — rejected. dbt Cloud Developer plan has a ~3,000 model-runs/month cap; cheap monthly aggregates keep BI tools off the heavier facts and prevent Tableau Public's row-limit (15M rows) from biting on the busiest dashboards.

## Consequences

- **Positive:** Schema is dimensionally correct, point-in-time correct via SCD2, and pre-aggregated where Tableau Public's free-tier limits make on-the-fly aggregation risky. Reviewers familiar with Kimball can read the schema and understand it without explanation.
- **Negative / cost:** 11 tables to build, test, and document. The `pit_join_company` macro is non-trivial and needs careful testing on SCD2 edge cases (effective-from = effective-to, multiple same-day events).
- **Follow-ups required:** `feat/gold-dbt` implements all 11 tables. Each fact gets `dbt test` coverage for not-null PKs, FK joins to dims, and accepted-values constraints on dimensional attributes. Aggregate tables get a refresh schedule tied to Silver freshness (no point recomputing if the underlying facts haven't changed).

## Amendments

### 2026-06-06 — 7th fact `fact_insider_trade` (Gold 11→12 tables)

The deferred 7th fact has landed. [ADR-0012](0012-insider-trades-phase-3-sec-edgar.md) dropped `fact_insider_trade` from Phase 1/2; Phase 3 (`feat/sec-edgar-insiders`) recovered it from SEC EDGAR Form 4. Gold is now **12 tables = 7 facts + 3 dims + 2 aggregates**.

**Added fact:**
- `fact_insider_trade` — Form 4 insider transactions, one row per **transaction line** `(accession, transaction_table, line_index)`; non-derivative + derivative lines (holdings excluded). Reporting-owner relationship flags + transaction code/shares/price + derivative terms. Incremental + merge + 90-day lookback. Source `silver.sec.insider_transactions`. Joins `dim_company` via `pit_join_company` on `transaction_date`. **1,175 rows** in `gold.marts.fact_insider_trade`.

Notes consistent with the original decision:
- It reuses the established **event-fact pattern** (`fact_dividend_event`/`fact_split_event`): incremental merge, lookback window, `pit_join_company`. No new architectural shape.
- Its Silver source is in schema `sec`, not `fmp`, so dbt needed a **second source block** (`silver_sec`) — a source carries one schema. This is a dbt mechanics detail, not a schema-design change.
- The Spark reserved word `table` (Silver column name) is renamed to `transaction_table` in the fact to keep it usable in `unique_key`/merge.
- EDGAR-specific ingestion decisions live in **[ADR-0024](0024-sec-edgar-form4-ingestion.md)**.

## References

- Kimball, *The Data Warehouse Toolkit*, 3rd ed.
- `option-b-stop-and-pure-flamingo.md` plan file — schema volume estimates
- [ADR-0002](0002-medallion-layer-ownership.md) — layer ownership (Gold = dbt)
- [ADR-0012](0012-insider-trades-phase-3-sec-edgar.md) — why `fact_insider_trade` is absent

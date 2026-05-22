# 0011 — FMP fundamentals capped at 5 records per call; Silver handles partial history

- **Status:** Accepted
- **Date:** 2026-05-22 (decision dated 2026-05-19)
- **Deciders:** project owner

## Context

FMP's free tier caps responses from six fundamental-data endpoints — `income-statement`, `balance-sheet-statement`, `cash-flow-statement`, `key-metrics`, `earnings`, `dividends`, `splits` — at the **5 most recent records** per call. There is no `limit=` parameter that recovers more on the free tier. `key-metrics` additionally restricts to annual cadence only on free tier.

This means the day-1 Bronze snapshot for each ticker contains, at most, the trailing 5 quarters of income/balance/cash-flow data (or 5 fiscal years for `key-metrics`). Full historical depth is unavailable from this source on free tier.

## Decision

Accept the 5-record cap as a hard constraint of the free-tier architecture. Ingest stores whatever FMP returns, with no special-case retry or "incomplete history" error. Bronze records every snapshot; Silver's SCD2 logic accretes history *forward* over time as new refreshes arrive (a record that was the "5th most recent" today drops off tomorrow but is preserved in Bronze and accumulated in Silver). Within ~5 quarters of operating the pipeline daily, Silver will have a complete rolling history from day-1 forward; pre-day-1 history is simply not recoverable from FMP.

## Considered alternatives

- **Pay for FMP starter (~200k calls/month, no row caps)** — rejected per free-tier-only constraint.
- **Backfill from another free source** — explored; no free fundamentals source offers full history without the same kind of caps. SEC EDGAR has the raw 10-K/10-Q XBRL data and is the principled answer, but parsing XBRL is a substantial sub-project ([ADR-0012](0012-insider-trades-phase-3-sec-edgar.md) parks SEC EDGAR work to Phase 3; full-fundamentals backfill could ride along).
- **Error / refuse to write when result has <5 records** — rejected. Some tickers legitimately have fewer historical fundamental filings (e.g., recent IPOs); the right behavior is "store what's there" not "refuse to store."

## Consequences

- **Positive:** Pipeline runs to completion on day 1 with no special-case backfill logic. Silver layer's forward-accreting SCD2 model is the right design for a continuously-refreshing pipeline anyway. Honest portfolio narrative: "free-tier limitation X; here's how the architecture accommodates it without dropping data."
- **Negative / cost:** First several months of operation have thin historical depth on fundamentals. BI dashboards that depend on YoY fundamentals comparisons need a "data range: from YYYY-MM-DD" annotation. Silver-layer tests can't assert against pre-day-1 fundamental records.
- **Follow-ups required:** Silver DLT pipelines (`feat/silver-dlt`) must use forward-only CDC keyed by `(ticker, period_end_date)`; new appearances of a fundamental row are inserts, not updates. Gold facts (`fact_financial_statement`, `fact_key_metric`) document the partial-history range in their `dbt docs` description. Phase 3 SEC EDGAR ingestion ([ADR-0012](0012-insider-trades-phase-3-sec-edgar.md)) can optionally backfill historical fundamentals from XBRL filings.

## References

- FMP free-tier docs — https://site.financialmodelingprep.com/developer/docs/stable (5-record cap visible per endpoint)
- Plan file `~/.claude/plans/resuming-feat-ingest-scaffold-work-on-shimmering-kazoo.md` — doc-walk findings 2026-05-19
- [ADR-0012](0012-insider-trades-phase-3-sec-edgar.md) — SEC EDGAR planned for Phase 3 (could subsume fundamentals backfill)

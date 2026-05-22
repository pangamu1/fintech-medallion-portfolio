# 0009 — Alpha Vantage downgraded to cross-validation; FMP promoted as primary daily-price source

- **Status:** Accepted
- **Date:** 2026-05-22 (decision dated 2026-05-18)
- **Deciders:** project owner

## Context

The original architecture had Alpha Vantage as the primary daily OHLCV source — `TIME_SERIES_DAILY?outputsize=full` was documented (in older sources) to return 20+ years of history on the free tier. During the CP7.1 smoke test on 2026-05-18, the endpoint returned a premium-feature rejection:

> The outputsize=full parameter value is a premium feature for the TIME_SERIES_DAILY endpoint.

Free-tier AV now ships only `outputsize=compact` (100 trading days). That's enough for cross-validation against another source but nowhere near the depth a portfolio's `fact_stock_daily` needs.

FMP's `historical-price-eod/full` returns the full daily-price history on the free tier with no per-call row cap (only the 250-calls/day quota and 85-ticker allowlist apply — see [ADR-0010](0010-tickers-swap-fmp-allowlist.md)). It was already in the endpoint catalog as a redundant source. The free-tier landscape had simply shifted under us.

## Decision

Alpha Vantage's role is downgraded to **cross-validation only**, using a single endpoint (`TIME_SERIES_DAILY` in compact mode, 100 days). FMP's `historical-price-eod/full` is promoted to the **primary** source for `fact_stock_daily`. Silver-layer reconciliation logic compares the 100-day AV window against the corresponding FMP slice and surfaces discrepancies via DLT Expectations.

## Considered alternatives

- **Pay for AV premium tier** — rejected per the free-tier-only project constraint.
- **Drop AV entirely; rely on FMP alone** — rejected. Two independent free sources with reconciliation is a stronger portfolio story than single-source ingestion ("here's how I handle source disagreement" is a real data-engineering skill). Cost of keeping AV is one extra endpoint and 10 calls/day.
- **Switch primary to yfinance or another unofficial Yahoo wrapper** — rejected. yfinance has no API contract, breaks on Yahoo HTML changes, and using it in a portfolio project signals "I don't read terms of service." FMP is a documented commercial API with a real free tier.
- **Scrape exchange websites directly** — rejected. Not free in time, brittle, ToS-questionable.

## Consequences

- **Positive:** Portfolio narrative upgrades from "redundant free sources" to "redundant free sources *with reconciliation logic*" — strictly better. AV's role is now well-scoped and won't bloat the rate budget (10/day vs the 25/day cap).
- **Negative / cost:** Silver layer carries reconciliation code it wouldn't otherwise need. AV's 100-day window is narrower than the FMP slice it cross-validates against, so reconciliation only covers the trailing 100 days.
- **Follow-ups required:** Silver DLT pipeline (`feat/silver-dlt`) must implement the FMP↔AV reconciliation as a `@dlt.expect_or_log` (not `_or_drop` — we want visibility, not gatekeeping). Cross-source discrepancy thresholds (e.g., >0.5% close-price drift) are open for tuning.

## References

- AV free-tier policy as observed 2026-05-18 — error message captured in plan file `~/.claude/plans/resuming-feat-ingest-scaffold-work-on-shimmering-kazoo.md` line 481
- FMP `/historical-price-eod/full` docs — https://site.financialmodelingprep.com/developer/docs/stable
- [ADR-0010](0010-tickers-swap-fmp-allowlist.md) — FMP free-tier 85-ticker allowlist (relevant because FMP is now the *primary* source)

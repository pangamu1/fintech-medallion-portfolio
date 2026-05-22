# 0010 — TICKERS swap (GOOG→GOOGL, BRK-B→PYPL) forced by FMP free-tier 85-ticker allowlist

- **Status:** Accepted
- **Date:** 2026-05-22 (decision dated 2026-05-19)
- **Deciders:** project owner

## Context

The original 10-ticker universe was `AAPL, MSFT, AMZN, META, TSLA, JPM, JNJ, NVDA, BRK-B, GOOG`. During the FMP doc walk on 2026-05-19, we discovered that most per-symbol FMP endpoints (income-statement, balance-sheet, cash-flow, key-metrics, historical-price-eod, earnings, dividends, splits) restrict free-tier callers to a documented 85-ticker allowlist. **Both** `BRK-B` and `GOOG` are outside that allowlist; only `BRK.B`/`BRK-A` and `GOOGL` (Class A voting shares) are included. The `profile` endpoint is the only allowlist-exempt per-symbol call.

This wasn't a "go pay for premium" moment — it was "swap to in-allowlist substitutes that preserve the SCD2 and corporate-action narratives the original picks were chosen for." See [ADR-0009](0009-alpha-vantage-downgrade-fmp-primary-prices.md) for context on why FMP became the primary source whose allowlist now binds.

## Decision

Final TICKERS list (10): `AAPL, MSFT, AMZN, META, TSLA, JPM, JNJ, NVDA, GOOGL, PYPL`.

- **GOOG → GOOGL** — both are Alphabet share classes; GOOGL is Class A (voting), GOOG is Class C (non-voting). Same issuer, identical fundamentals, near-identical price series. Preserves the "dual-class share structure" narrative (and arguably strengthens it — GOOGL is the canonical Class A ticker analysts cite).
- **BRK-B → PYPL** — BRK-B was originally chosen for "no-dividend stock + Berkshire-specific holding structure"; PYPL also pays no dividend, plus it carries the 2015 eBay spinoff (a meaningful corporate action SCD2 will need to handle for `dim_company`). Strictly more interesting than BRK-B for the portfolio story.

## Considered alternatives

- **Drop GOOG and BRK-B; ship with 8 TICKERS** — rejected. 8 is too narrow to exercise the cross-sector SCD2 events the universe was designed around. Two near-cost substitutions buy a full 10-ticker universe.
- **Pay for FMP starter ($14/mo)** — rejected per the free-tier-only project constraint.
- **Use Alpha Vantage as primary so the allowlist doesn't apply** — rejected; AV's free-tier shrank to 100-day windows ([ADR-0009](0009-alpha-vantage-downgrade-fmp-primary-prices.md)).
- **Mix tickers: pull GOOG from AV only, pull rest from FMP** — rejected. Adds source-routing logic for one ticker, breaks the symmetry of the ingest scripts, and AV's 100-day window doesn't give GOOG the historical depth `fact_stock_daily` needs.

## Consequences

- **Positive:** Universe stays at 10, sector diversity preserved, and PYPL upgrades the "no-dividend" slot with an additional corporate-action narrative. All 10 tickers are guaranteed callable across the full FMP endpoint set.
- **Negative / cost:** Anyone reading early planning docs that still say "GOOG" or "BRK-B" will be briefly confused. The historical-doc cleanup is handled in `chore/claude-md-purify`.
- **Follow-ups required:** `dim_company` must surface the share-class for GOOGL (so a future Class C add is a clean SCD2 insert, not an update). `fact_dividend_event` will be empty for PYPL — confirms the null-handling code path.

## References

- FMP free-tier symbol allowlist — observed during doc walk 2026-05-19; ticker list at https://site.financialmodelingprep.com/developer/docs/stable
- Plan file `~/.claude/plans/resuming-feat-ingest-scaffold-work-on-shimmering-kazoo.md` — discovery notes 2026-05-19
- [ADR-0009](0009-alpha-vantage-downgrade-fmp-primary-prices.md) — why FMP is the primary source whose allowlist binds

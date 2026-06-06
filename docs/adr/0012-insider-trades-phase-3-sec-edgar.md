# 0012 — Insider trades deferred to Phase 3 via SEC EDGAR Form 4

- **Status:** Accepted
- **Date:** 2026-05-22 (decision dated 2026-05-19)
- **Deciders:** project owner

## Context

The original Gold-schema plan included `fact_insider_trade` and a `dim_insider` dimension, sourced from FMP. During the 2026-05-19 doc walk we discovered that FMP's two per-symbol insider endpoints — `Search Insider Trades` and `Search Insider Trades By Reporting Name` — are paywalled (premium-only). The single free endpoint, `/insider-trading/latest`, is a global activity feed across all symbols with no `symbol=` filter; it can't populate a per-ticker fact table.

Insider activity is genuinely high-signal portfolio content — quant strategies routinely use Form 4 filings, and being able to ingest and analyze them is a real data-engineering credential. We don't want to drop it; we want to source it correctly.

The principled source is **SEC EDGAR**: insiders file Form 4 within 2 business days of any reportable transaction, directly with the SEC, in structured XML. EDGAR is free, generously rate-limited (10 req/sec), has no symbol allowlist, no row-count caps, and demonstrates a different ingestion skill (structured XML parsing vs JSON).

## Decision

`fact_insider_trade` and `dim_insider` are dropped from Phase 1 (local Python ingestion) and Phase 2 (Bronze/Silver/Gold/BI). The capability is recovered in a new **Phase 3** via SEC EDGAR Form 4 ingestion, on a future branch (provisionally `feat/sec-edgar-insiders`). The current Gold schema in [ADR-0013](0013-gold-star-schema.md) shows 6 facts and reflects this drop.

## Considered alternatives

- **Pay for FMP starter** — rejected per free-tier-only constraint.
- **Scrape `/insider-trading/latest` and filter client-side** — rejected. The feed isn't archived; we'd only ever have data from the moment we started scraping, with no backfill capability. Also fragile (no contract that the feed shape is stable).
- **Use a third-party wrapper around EDGAR (e.g., `sec-api.io`)** — rejected. Adds a paid dependency that the SEC itself provides for free.
- **Pull insider data from yfinance** — rejected (same reasoning as in [ADR-0009](0009-alpha-vantage-downgrade-fmp-primary-prices.md): unofficial, no API contract, breaks silently).

## Consequences

- **Positive:** Phase 3 demonstrates structured-XML ingestion and SEC EDGAR integration — both genuinely valuable portfolio credentials that the FMP-only path wouldn't show. The project's BI dashboard list goes from 8 archetypes to 7 in Phase 2, then back to 8 in Phase 3.
- **Negative / cost:** "Insider activity" dashboard is unavailable until Phase 3 ships. Phase 3 requires parsing Form 4 XML (ownership document format), which is non-trivial.
- **Follow-ups required:** `feat/sec-edgar-insiders` branch when Phase 2 completes. ADR-NNNN (Phase 3 era) will document the EDGAR ingestion design, rate-limit handling, and Form 4 schema mapping. SEC EDGAR's User-Agent header policy must be honored (descriptive UA with contact info, per their fair-use policy).

## Amendments

### 2026-06-06 — Phase 3 shipped; insiders recovered (deferral reversed)

The deferral this ADR records is now **reversed**. `feat/sec-edgar-insiders` (Phase 3) ingested SEC EDGAR Form 4 for the 10-ticker universe through the full medallion stack and landed `fact_insider_trade` in Gold — **1,175 rows** in `gold.marts.fact_insider_trade`, matching Silver exactly.

What shipped, by layer:
- **Ingest** (`fintech_datalake/scripts/ingest_sec_edgar.py`, PR #26 `20800af`) — keyless EDGAR client; ticker→CIK from `company_tickers.json`; 30 most-recent Form 4 per ticker; **XML parsed to normalized JSON at ingest** (one record per transaction line). 1,180 records / 10 files.
- **Bronze** (`bronze.sec.insider_transactions`, Autoloader, PR #26) — 1,180 rows, rescue-clean.
- **Silver** (`silver.sec.insider_transactions`, DLT event table, PRs #27/#28) — 1,175 rows; forward-only (no SCD2, like `dividends`/`splits`); scoped to our own securities via `ticker = issuer_symbol` (drops outbound >10%-owner stakes, e.g. Alphabet→LIFE).
- **Gold** (`gold.marts.fact_insider_trade`, dbt incremental, PR #29 `45d00d2`) — 7th fact; joined to `dim_company` via `pit_join_company` on `transaction_date`; rode CI/CD to prod with zero manual steps.

The "ADR-NNNN (Phase 3 era)" follow-up promised in the Consequences section is **[ADR-0024](0024-sec-edgar-form4-ingestion.md)** (EDGAR ingestion design, rate-limit/User-Agent handling, Form 4 field map). Gold's fact inventory in [ADR-0013](0013-gold-star-schema.md) is amended 6→7 facts (11→12 tables). The two paywalled FMP findings in the Context above remain accurate — EDGAR, not FMP, is the source.

## References

- SEC EDGAR Form 4 documentation — https://www.sec.gov/forms (Form 4: "Statement of Changes in Beneficial Ownership")
- SEC EDGAR fair-access policy — https://www.sec.gov/os/accessing-edgar-data
- Plan file `~/.claude/plans/resuming-feat-ingest-scaffold-work-on-shimmering-kazoo.md` — doc-walk findings 2026-05-19
- [ADR-0013](0013-gold-star-schema.md) — Gold schema reflects the Phase 1/2 drop of `fact_insider_trade`

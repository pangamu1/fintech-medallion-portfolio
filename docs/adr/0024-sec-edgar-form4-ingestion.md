# 0024 — SEC EDGAR Form 4 ingestion: parse-at-ingest, bounded backfill, keyless User-Agent client

- **Status:** Accepted
- **Date:** 2026-06-06 (decisions locked 2026-06-04)
- **Deciders:** project owner

## Context

[ADR-0012](0012-insider-trades-phase-3-sec-edgar.md) deferred `fact_insider_trade` to a Phase-3 SEC EDGAR source and promised a follow-up ADR documenting the EDGAR ingestion design, rate-limit handling, and Form 4 schema mapping. This is that ADR.

SEC EDGAR is a genuinely different source from the FMP/Alpha Vantage REST-JSON pattern the rest of the project uses, and it forced several design decisions a CP0 live spike (2026-06-04) resolved against real responses:

- **Multi-hop API, no single endpoint.** Getting one company's Form 4 transactions takes three hops: ticker→CIK (`company_tickers.json`), CIK→filing list (`data.sec.gov/submissions/CIK{cik10}.json`), filing→document (`www.sec.gov/Archives/edgar/data/{cik}/{accession}/form4.xml`).
- **Form 4 is XML, not JSON.** Root `ownershipDocument`; every real value sits under a `/value` leaf; `nonDerivativeTable` mixes `nonDerivativeTransaction` (has date+code) with `nonDerivativeHolding` (no date/code); `derivativeTable` adds conversion price + underlying-security fields. `transactionPricePerShare` can be price-less (footnote-only, e.g. RSU code `M`).
- **High filing volume.** AAPL alone showed 587 Form 4 in the recent page (~53/yr) — unbounded backfill is a real free-tier/politeness risk.
- **Keyless but politeness-gated.** EDGAR needs no API key, but returns 403 without a descriptive `User-Agent` and enforces fair-access at ≤10 req/s.
- **A Form 4 is indexed under both issuer and reporting-owner CIK.** A company's submissions feed therefore includes its *outbound* >10%-owner stakes in *other* companies (observed: GOOGL's feed carried 5 filings where the issuer was `LIFE`).

All hypotheses were confirmed against live responses before any ingestion code was committed.

## Decision

We ingest SEC EDGAR Form 4 for the 10-ticker universe with the following locked decisions:

1. **Parse XML → normalized flat JSON at ingest.** The Python ingester parses `ownershipDocument` and lands clean, flat JSON (one record per transaction line) in the lake. Bronze stays on the established Autoloader + `explode`-friendly JSON path; no XML touches Spark. Consistent with [ADR-0019](0019-alpha-vantage-deferred-from-bronze.md)'s "land the shape Bronze wants" stance.
2. **Bounded backfill: 30 most-recent Form 4 per ticker.** `SEC_MAX_FILINGS_PER_TICKER = 30`. Small, deterministic, full-history for low-filers (JPM/JNJ), mirrors the FMP 5-cap discipline ([ADR-0011](0011-fmp-fundamentals-five-record-cap.md)). `4/A` amendments are **deferred** (filter `form == "4"` only).
3. **Keyless client with descriptive User-Agent + ≤10 req/s pacing.** `requests.Session` + retry adapter; UA `fintech-medallion-portfolio piruthviraj7@gmail.com` pinned on the session. The UA is **not a secret** (broadcast on every request) → it lives as a plain constant in `config.py`, never in `.env`. No token anywhere.
4. **Forward-only event table, no SCD2.** Insider transactions are events like `dividends`/`splits`; Silver dedups by `(accession, table, line_index)` and never historizes.
5. **Universe scoping at Silver: `ticker = issuer_symbol`.** Keeps Gold grain = "insider trades in *our* 10 companies' stock," dropping the outbound >10%-owner filings that a company's submissions feed carries (1,180 → 1,175). The soft `symbol_matches` DLT expectation is retained as a now-guaranteed invariant / tripwire.
6. **Gold grain = one transaction line.** Holdings excluded; a single Form 4 fans out to multiple `fact_insider_trade` rows.

## Considered alternatives

- **Land raw Form 4 XML in Bronze, parse in Silver** — rejected. Pushes XML parsing into Spark (`spark-xml` / UDFs), fights the Autoloader `explode(array)` pattern every other Bronze stream uses, and concentrates the hardest logic in the layer least suited to it. Parsing at ingest keeps the novelty in Python where it's testable.
- **Full-history backfill** — rejected. Thousands of filings across 10 tickers risks the 10 req/s ceiling and adds no analytical value over a recent window for a portfolio demo. 30/ticker is the FMP-cap analogue.
- **Include `4/A` amendments now** — deferred. Amendments need supersession logic (which original line does an `4/A` replace?); out of scope for the first pass.
- **SCD2 on insider transactions** — rejected. They're append-only events, not slowly-changing attributes; SCD2 would be meaningless overhead.
- **No universe scoping (keep all filings in the feed)** — rejected. Outbound >10%-owner stakes (Alphabet→LIFE) are transactions in *other* companies' securities; including them breaks the fact's grain and would orphan rows with no `dim_company` match for the foreign issuer.

## Consequences

- **Positive:** Demonstrates structured-XML ingestion + a multi-hop public-API integration — credentials the FMP-only path couldn't show. The full vertical slice (ingest→Bronze→Silver→Gold→docs) rode the existing CI/CD with zero manual prod steps, validating `feat/ci-cd`. Recovers the [ADR-0012](0012-insider-trades-phase-3-sec-edgar.md) deferral. Zero AV/FMP budget consumed (EDGAR is free + keyless).
- **Negative / cost:** The 30-filing window means recent-only insider history (not full history for high-filers like TSLA/META). Parse-at-ingest couples the ingester to the Form 4 XML contract — a schema change at SEC breaks parsing rather than being rescued downstream. `4/A` corrections are not yet reflected, so a superseded transaction line can persist.
- **Follow-ups required:** if full history or `4/A` handling is wanted, a future branch widens the backfill window + adds amendment supersession. Form 4 transaction-code taxonomy (P/S/A/M/F/G…) is currently passed through untyped; an `accepted_values`/decode mapping could harden the Gold fact.

## References

- [ADR-0012](0012-insider-trades-phase-3-sec-edgar.md) — the Phase-3 deferral this ADR's source reverses.
- [ADR-0013](0013-gold-star-schema.md) — Gold star schema; gains `fact_insider_trade` as the 7th fact.
- [ADR-0011](0011-fmp-fundamentals-five-record-cap.md) — the record-cap discipline the 30-filing window mirrors.
- [ADR-0018](0018-bronze-pyspark-autoloader-supersedes-copy-into.md) — Bronze Autoloader pattern the new `bronze.sec` stream slots into.
- [ADR-0019](0019-alpha-vantage-deferred-from-bronze.md) — "land the shape Bronze wants" precedent for parse-at-ingest.
- [ADR-0021](0021-gold-implementation-refinements.md) — `pit_join_company` half-open join + `dim_company` `1900-01-01` floor that lets historical insider dates resolve a `company_key`.
- [ADR-0007](0007-bronze-ingestion-durability-atomic-writes-jsonl-logs.md), [ADR-0008](0008-twelve-factor-secrets-via-dotenv.md) — ingestion durability + secrets conventions the EDGAR client follows.
- SEC EDGAR fair-access policy — https://www.sec.gov/os/accessing-edgar-data
- Ticker→CIK map — https://www.sec.gov/files/company_tickers.json
- Filing history API — https://data.sec.gov/submissions/CIK{cik10}.json

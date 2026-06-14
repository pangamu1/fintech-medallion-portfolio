# 0025 — BI consumption layer: Tableau Public via a Google-Sheets reverse-ETL serving layer (not a live warehouse connection)

- **Status:** Accepted
- **Date:** 2026-06-12 (decisions locked at CP0, 2026-06-07; suite built through 2026-06-12)
- **Deciders:** project owner

## Context

The architecture diagram's downstream end — `BI/Quant/Exec` — had no implementation. The Gold star schema ([ADR-0013](0013-gold-star-schema.md)) names **Tableau Public** as the BI target but never says *how* Tableau reaches the warehouse. A feasibility spike (2026-06-03/04) plus CP0 recon (2026-06-07) resolved that against reality:

- **Tableau Public has no Databricks connector.** The free tier can read **Google Sheets** (and a handful of cloud sources), but not a Databricks SQL warehouse. "Tableau on the warehouse" is therefore impossible as a *live* connection on the free tier — it must go through an intermediate source Tableau Public *can* read.
- **A published Tableau Public viz is a self-contained extract.** Viewers never authenticate; the OAuth re-prompt the spike hit is **authoring-only** (Tableau Public doesn't persist cloud creds like Desktop does). Confirmed: a Sheets-backed *published* viz auto-refreshes server-side ~every 24h — a CSV-on-Drive source does **not** get that scheduled refresh.
- **Unattended writes need a service account, not interactive OAuth.** A scheduled job can't click through an OAuth consent screen; the write side must be key-based (Google service-account JSON).
- **Sheets has a ~10M-cell cap.** All curated marts together are well under it (the full 10-mart serve is ~300K cells), so the cap is not a binding constraint for this universe.
- **Databricks Free Edition scheduled jobs were inconclusive in the docs** — so the orchestrator decision routes *around* Databricks scheduling rather than depending on it.

## Decision

Build the BI layer as a **reverse-ETL serving layer feeding Tableau Public**, with these locked decisions:

1. **Single channel: Tableau Public.** The CP0 "two-channel" option (a second, live **Databricks native AI/BI Dashboards** channel on `gold.marts`) was **cut** for scope — one honest, recruiter-facing public artifact beats two half-built ones. Databricks Dashboards remain trivially addable later.
2. **Serving layer = `serve_to_sheets.py` (reverse-ETL).** `databricks-sql-connector` runs `SELECT *` on each curated Gold mart from the SQL warehouse; `gspread` writes each result to one tab in a single Google Sheet (tab name = the segment after the last dot in the FQN). Date/`Decimal`/`None` coerced to Sheet-safe cells; tab resized + cleared before write. Follows ingestion conventions (logging, fail-fast env).
3. **Google service-account auth (key-based, non-interactive).** A GCP project (`fintech-bi-serving`) with Sheets + Drive APIs enabled; SA `bi-sheets-writer@…`; the target Sheet is shared *Editor* with the SA email. The JSON key is **not** in the repo — it's a GitHub Actions secret (`GOOGLE_SERVICE_ACCOUNT`), TF-managed via `github_actions_secret`, same pattern as the `DBT_CLOUD_*` / `DATABRICKS_*` secrets. The Sheet ID is **not** a secret (access is gated by the share + the viz is public anyway) → it's a plain constant in `config.py`.
4. **Orchestrator = weekly GitHub Action cron.** `.github/workflows/bi-refresh.yml` (`cron: "0 6 * * 1"` + `workflow_dispatch`) installs deps with `uv`, writes the SA key to `$RUNNER_TEMP`, and runs `serve_to_sheets.py` with `DATABRICKS_HOST` / `DATABRICKS_TOKEN` / `DATABRICKS_HTTP_PATH` + `GOOGLE_SERVICE_ACCOUNT` from secrets. `DATABRICKS_HTTP_PATH` was added as the 6th TF-managed GitHub secret (non-sensitive, like the host). GHA is serverless (GitHub hosts the cron + ephemeral runner — zero always-on infra), reuses the CI muscle, and sidesteps the Databricks-scheduling unknown.
5. **Cadence = weekly write; Tableau's own ~24h poll keeps the published viz fresh.** The GHA refreshes the Sheet weekly; Tableau Public re-extracts on its own server-side schedule. No manual intervention once published.
6. **Served marts = all 10 Gold marts, one tab each.** `dim_company`, `agg_company_monthly`, `agg_sector_daily`, and the 7 facts (`fact_stock_daily`, `fact_earnings_event`, `fact_financial_statement`, `fact_key_metric`, `fact_dividend_event`, `fact_split_event`, `fact_insider_trade`). CP0 locked a 4-mart serving set; CP4 expanded it to 10 once dashboard design showed most of the star schema (earnings, fundamentals, ratios, dividends, splits, daily OHLCV) was otherwise never reaching the BI layer. `dim_date` / `dim_fiscal_period` are excluded — dates are derived in Tableau.
7. **Dashboard suite = 4 boards** on `public.tableau.com`: **Company Deep-Dive** (parameter-driven single-ticker 360°: candlestick + volume, earnings beat/miss, fundamentals, dividends, insider, KPI tiles; `pTicker` + `pWindowYears` controls), **Executive Overview** (cross-ticker KPIs + gainers/losers + sector heatmap), **Sector & Market** (sector ranking + trend + filter/highlight dashboard actions across two sources), and **Fundamentals & Valuation** (a parameter-driven Quality-vs-Value scatter / Metric Explorer + a drill-to-detail table, same-source filter action).

This **refines [ADR-0013](0013-gold-star-schema.md)**: the warehouse is reached by Tableau Public through a **Sheets serving-layer extract (weekly), not a live connection**. Same "documented-reality-vs-original-plan" pattern as the Pages-via-UI finding ([ADR-0022](0022-cicd-github-actions-dbt-cloud.md)).

## Considered alternatives

- **Live Tableau Public → Databricks connection** — impossible. Tableau Public's free tier has no Databricks connector; this is the constraint the whole serving layer exists to work around.
- **Databricks native AI/BI Dashboards as a second, live channel** — cut for scope (was the CP0 "both channels" lean). It tells the true "live warehouse BI" story with near-zero auth, and remains a cheap future add; it just isn't built here.
- **CSV on Google Drive instead of a Sheet** — rejected. The spike proved Tableau Public's scheduled ~24h refresh applies to **Sheets-backed** published vizzes, not Drive CSVs. A CSV would require manual re-publish to refresh.
- **Interactive OAuth for the Sheets write** — rejected. OAuth can't run unattended in a scheduled job; the write side must be a key-based service account.
- **Apache Airflow as the orchestrator** — rejected (again — same call as the unified-pipeline reasoning). Airflow's scheduler is an always-on daemon; that breaks the free-tier/no-ops constraint regardless of how rarely the job runs. GHA cron is serverless. Airflow belongs in a separate dedicated project.
- **Databricks scheduled job as the orchestrator** — rejected. Free-Edition scheduled-job support was inconclusive in the docs (Bronze ran `availableNow`, not cron); GHA routes around the unknown with infra we already manage.
- **Daily refresh cadence** — considered (matches Tableau Public's ~24h ceiling); chose **weekly** — the marts don't change faster than the upstream weekly ingest cadence, so a daily write would burn runs for no fresher data.
- **Serve only raw facts (e.g. `fact_stock_daily`) and aggregate in Tableau** — rejected for the heaviest views; the aggregates (`agg_*`) exist precisely to keep BI off the wide facts ([ADR-0013](0013-gold-star-schema.md)). Both are served so each dashboard picks the right grain.

## Consequences

- **Positive:** Implements the previously-empty downstream end of the architecture. Demonstrates a **reverse-ETL / serving-layer** pattern (warehouse → Sheets) and a recruiter-friendly public artifact, on top of genuine warehouse BI semantics (star schema, SCD2-aware point-in-time joins surfaced in a single-ticker deep-dive). Reuses the established TF-secrets + GHA-cron muscle ([ADR-0022](0022-cicd-github-actions-dbt-cloud.md)); zero AV/FMP budget (Databricks SQL reads are tiny, GHA minutes free, Google + Tableau Public free).
- **Negative / cost:** The published viz is an **extract refreshed ~daily/weekly, not live** — latency is the honest tradeoff of the no-connector free tier. A new Gold mart must be added to `config.BI_MARTS` *and* re-connected in Tableau (two places). The serving layer couples to the Sheet's cell/format quirks (the `_to_cell` coercion). Tableau workbooks live in the app, not the repo, so the dashboard definitions are not version-controlled here.
- **Known data-correctness debt (deliberate, deferred):** `agg_company_monthly.monthly_close` is **raw/unadjusted** (`max_by(close_price)` over `silver.daily_prices`, not `adj_close`), so any Tableau metric built on it (e.g. a trailing-return calc) is **split-distorted** when a split falls inside the window. Chosen "design now, correctness post-publish." Fix options: rebuild the metric on `fact_stock_daily.adj_close` with date anchors, or add a monthly `adj_close` to `agg_company_monthly.sql` and re-serve.
- **Phase D — DONE (2026-06-14).** The 4-board suite is published at **<https://public.tableau.com/app/profile/piruthviraj.a.s/viz/FinTechMedallion-MarketAnalytics/ExecutiveOverview>** (owner's account; **Executive Overview is the hub/landing**). Pre-publish polish completed (C1's `Candle Direction` / `Surprise Direction` / A/D encodings retouched to the custom `Gain / Loss` palette).
  - **Hub-and-spoke nav, not tabs:** Tableau Public's save dialog exposes no "Show Sheets as Tabs," so navigation is built from **Navigation button objects** — a hub (Executive Overview) with 4 outbound buttons + a `← Overview` back-button on each spoke. Single-click for published viewers (Option+click in Desktop authoring).
  - **Uniform 1200×1500 canvas — documented-reality finding:** a published Tableau Public workbook renders all dashboards in **one shared, fixed-size viz container** that does **not** resize per sheet on navigation. Mixed sizes (Company Deep-Dive 1500 vs the rest 900) clipped the taller board to the landing page's height. Fix = standardize **all** dashboards to one fixed size (1200×1500). Same "documented-reality-vs-original-plan" pattern as the Pages-via-UI finding ([ADR-0022](0022-cicd-github-actions-dbt-cloud.md)).
  - **Auto-refresh NOT yet activated** — Google is not connected in Tableau Public's web settings, so the published viz is currently a **static snapshot**, not the ~24h auto-refresh this ADR's Decision assumes. Deferred follow-up: Settings → Connected Accounts → connect Google → enable data-source sync, then confirm a refresh after a `bi-refresh` GHA run. (The `agg_company_monthly.monthly_close` split-distortion debt above remains deferred too.) Optionally add the Databricks Dashboards channel.

## Note — config secrets refactored to lazy accessors (refines [ADR-0008](0008-twelve-factor-secrets-via-dotenv.md))

CP-B of this branch converted `config.py`'s secrets from **eager module-level** `_required_env(...)` constants to **lazy accessor functions** (`fmp_api_key()`, `databricks_host()`, `databricks_token()`, `databricks_http_path()`, etc.), updating all call sites across `ingest_alpha_vantage.py`, `ingest_fmp.py`, and `serve_to_sheets.py`. **Why:** the BI job needs the Databricks + Google credentials but **none of the AV/FMP keys**; eager loading made *every* script fail-fast on *every* secret at import, so the reverse-ETL job would have demanded API keys it never uses. Lazy accessors move the fail-fast boundary from **import-time to first-use**, so each entry point only requires the secrets it actually reads. The fail-fast guarantee of [ADR-0008](0008-twelve-factor-secrets-via-dotenv.md) is preserved — it just fires at the call site instead of at import.

## References

- [ADR-0013](0013-gold-star-schema.md) — Gold star schema; names Tableau Public as the BI target. This ADR refines *how* Tableau reaches it (Sheets serving-layer extract, not live).
- [ADR-0022](0022-cicd-github-actions-dbt-cloud.md) — the GitHub-Actions + TF-managed-secrets pattern this serving layer reuses (incl. the Pages-via-UI "documented reality" precedent).
- [ADR-0023](0023-two-tier-dbt-environments.md) — the `gold.marts` prod env the serving layer reads from.
- [ADR-0008](0008-twelve-factor-secrets-via-dotenv.md) — secrets convention refined to lazy first-use accessors (see Note above).
- [ADR-0014](0014-terraform-for-iac.md) — `github_actions_secret` mechanism for `GOOGLE_SERVICE_ACCOUNT` + `DATABRICKS_HTTP_PATH`.
- `fintech_datalake/scripts/serve_to_sheets.py`, `config.py` (`BI_*` block), `.github/workflows/bi-refresh.yml`.
- Tableau Public Google-Sheets refresh behavior — confirmed by spike, 2026-06-03/04.

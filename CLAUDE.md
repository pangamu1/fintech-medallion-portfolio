# CLAUDE.md — FinTech Portfolio Project Context

## Behavioral Rules
- Never assume or speculate about files you have not opened. Always read before answering.
- Always provide hallucination-free answers grounded in what is actually present in the code.
- Never state a specific value, config, or behavior as fact without having read the file that contains it. If uncertain, say "let me verify" and read the file before answering.
- When answering questions about configuration or behavior, always read the relevant file first — do not rely on memory or inference from prior context.
- When referencing code, include the file path and line number where relevant.
- Do not create files unless explicitly requested.
- Be direct and concise. Lead with the answer, not the reasoning.
- Be an extremely harsh critic when the user clarifies doubts. Do not validate with phrases like "Exactly right", "You've got it", "You nailed it", "Spot on", or any equivalent. Only confirm correctness when the answer is precisely correct per official documentations. If the user is even slightly off, correct them immediately and explain why.

## Project Goal
End-to-end FinTech data engineering portfolio project. Replicates a real production stock-market data platform using only free editions of industry-standard tools. Target: MAANG-level production quality. No paid services.

## Reference Documents
- `fintech_data_ecosystem.svg` — upstream/downstream actor diagram.
- ADRs under `docs/adr/` — append-only decision log in MADR format. See [Decision Log](#decision-log) below.
- Per-branch plan files at `~/.claude/plans/<branch>.md` — operational state (not in repo).
- Auto-memory at `~/.claude/projects/<project-id>/memory/` — operational connection facts, role, preferences (not in repo).

## Decision Log
Architectural decisions are recorded as immutable [MADR-format](https://adr.github.io/madr/) ADRs under [`docs/adr/`](docs/adr/). A new ADR is written for every significant choice; reversals happen by writing a superseding ADR, never by editing history. Template at [`docs/adr/0000-template.md`](docs/adr/0000-template.md).

Currently published:

- [ADR-0001 — Record architecture decisions in MADR format](docs/adr/0001-record-architecture-decisions.md)
- [ADR-0002 — Medallion layer ownership: Python / Databricks / DBT](docs/adr/0002-medallion-layer-ownership.md)
- [ADR-0003 — Use `uv` for Python dependency management](docs/adr/0003-uv-for-python-dependency-management.md)
- [ADR-0004 — Initialize the Python project in application mode, not package mode](docs/adr/0004-application-mode-not-package-mode.md)
- [ADR-0005 — LEARNING MODE: the user types every line of project source code](docs/adr/0005-learning-mode-no-claude-generated-code.md)
- [ADR-0006 — Use `.gitkeep` to commit empty data-lake directories](docs/adr/0006-gitkeep-for-empty-data-lake-directories.md)
- [ADR-0007 — Bronze ingestion durability: atomic writes and JSONL audit logs](docs/adr/0007-bronze-ingestion-durability-atomic-writes-jsonl-logs.md)
- [ADR-0008 — 12-factor secrets via `python-dotenv` and fail-fast env loading](docs/adr/0008-twelve-factor-secrets-via-dotenv.md)
- [ADR-0009 — Alpha Vantage downgraded to cross-validation; FMP promoted as primary daily-price source](docs/adr/0009-alpha-vantage-downgrade-fmp-primary-prices.md)
- [ADR-0010 — TICKERS swap (GOOG→GOOGL, BRK-B→PYPL) forced by FMP free-tier 85-ticker allowlist](docs/adr/0010-tickers-swap-fmp-allowlist.md)
- [ADR-0011 — FMP fundamentals capped at 5 records per call; Silver handles partial history](docs/adr/0011-fmp-fundamentals-five-record-cap.md)
- [ADR-0012 — Insider trades deferred to Phase 3 via SEC EDGAR Form 4](docs/adr/0012-insider-trades-phase-3-sec-edgar.md)
- [ADR-0013 — Gold layer is a Kimball star schema: 6 facts + 3 dims + 2 aggregates](docs/adr/0013-gold-star-schema.md)
- [ADR-0014 — Terraform for infrastructure as code (HCP Terraform Free + Databricks + GitHub providers)](docs/adr/0014-terraform-for-iac.md)
- [ADR-0015 — dbt Cloud Developer-plan API is usable; dbt Cloud TF management deferred to dedicated branch](docs/adr/0015-dbt-cloud-developer-api-usable.md)
- [ADR-0016 — Databricks Free Edition Default Storage; UC catalogs managed via UI + TF import, not TF create](docs/adr/0016-free-edition-default-storage-workaround.md)
- [ADR-0017 — Databricks Free Edition: `account admins` not a resolvable principal; UC grants pinned to workspace owner email](docs/adr/0017-free-edition-account-admins-principal-unavailable.md)
- [ADR-0018 — Bronze runs on PySpark Autoloader; supersedes `COPY INTO` for the Bronze layer](docs/adr/0018-bronze-pyspark-autoloader-supersedes-copy-into.md)
- [ADR-0019 — Alpha Vantage `TIME_SERIES_DAILY` deferred from Bronze; Silver consumes JSON directly](docs/adr/0019-alpha-vantage-deferred-from-bronze.md)

## Architecture (Authoritative)
```
Python ingest  →  Local JSON Lake  →  Databricks Free Edition  →  DBT Cloud (Developer free)  →  BI/Quant/Exec
                                       Bronze + Silver layers       Gold marts (star schema)
```

**Layer ownership — non-negotiable:**
| Layer | Owner | Logic |
|---|---|---|
| Ingestion | Python scripts (`fintech_datalake/scripts/`) | Hit Alpha Vantage + FMP, land JSON in local lake |
| Bronze | Databricks (PySpark Autoloader + Delta) | Raw, append-only, schema evolution via `cloudFiles.schemaEvolutionMode = "rescue"` (per [ADR-0018](docs/adr/0018-bronze-pyspark-autoloader-supersedes-copy-into.md)) |
| Silver | Databricks DLT pipelines (`@dlt.table`, `dlt.create_auto_cdc_flow`) | Cleansing, CDC, SCD2 history tables, late-arriving fix, DLT Expectations for data quality |
| Gold | DBT Cloud (Developer free) | Star schema dims + facts, tests, lineage docs |

**Silver owns CDC + SCD2. DBT does NOT do SCD2. DBT consumes the already-historized Silver SCD2 tables and surfaces them as Gold dimensions with surrogate keys.**

## Free-Tier Stack
- Databricks Free Edition (SQL Warehouse + Serverless DLT)
- DBT Cloud Developer plan (1 seat, ~3,000 model runs/month)
- GitHub (public repo, unlimited Actions minutes)
- GitHub Pages (host `dbt docs` site)
- HCP Terraform Free (planned, future branch)
- pre-commit + sqlfluff (local linting; future)

## DBT Project Conventions
- Project root: `fintech_dbt/`
- Layout: `models/marts/{core,finance}/`, `models/sources/`, `tests/`, `macros/`, `seeds/`
- Materializations: dims = `table`, facts = `incremental` with `merge` strategy + lookback window
- Surrogate keys: `dbt_utils.generate_surrogate_key` over `(natural_key, scd_effective_from)` for SCD2 dims
- Point-in-time join: `pit_join_company` macro joins facts to SCD2 dims via `event_date BETWEEN scd_effective_from AND COALESCE(scd_effective_to, DATE '9999-12-31')`
- Naming: `stg_*` (not used — no staging here), `dim_*`, `fact_*`, `int_*`, sources declared under `silver` schema

## CI/CD Conventions
- Branch → PR → GitHub Actions runs `pre-commit` + `dbt build --select state:modified+ --defer`
- Merge to `main` → DBT Cloud production job runs `dbt build` then `dbt docs generate`
- A follow-on Action publishes docs to GitHub Pages

## Working Style for This Project — LEARNING MODE (locked 2026-05-14)
- **Claude does NOT write code or create files directly.** Project source files (`*.py`, `*.toml`, `*.yml`, `.gitignore`, `.env*`, etc.) are typed entirely by the user. This is non-negotiable.
- Claude's job: explain the concept, explain *why* a line/block exists, then guide the user to type it themselves.
- Work in **small phases / blocks / snippets** — never an entire file or program in one go. A 30-line file gets built in ~5 chunks with checkpoints, not one paste.
- The user types every line. The user runs every command. Claude observes the output and explains what it means.
- This rule supersedes the original "Claude writes code when asked" framing. Even if the user says "write this for me", redirect: ask which part they want to learn first, then walk them through writing it.
- **Exception 1 — meta files:** plan files at `~/.claude/plans/` and this `CLAUDE.md` are *not* project source code; Claude edits them directly. The user reviews the diff.
- **Why:** the entire point of this project is portfolio-grade *understanding*. Code generated by Claude that the user can't explain in an interview is worse than no code at all.

## Response Style for LEARNING MODE Teaching (locked 2026-05-20)
Each teaching turn for a checkpoint or sub-step MUST follow this structure. This is required — not a suggestion.

### Required response shape
1. **What and why** (1–3 sentences max) — name the concern this sub-step addresses, lead with the answer not the rationale
2. **Reference shape** — show the EXACT code the user should type, in a fenced code block. Annotate each meaningful decision (style choices, library quirks, deliberate omissions) in a follow-up table
3. **Verification commands** — `uv run python -c "..."`, AST checks, `grep`, file inspection. Logic-only verification before any live API call
4. **Expected output** — show what success looks like literally, so the user can compare
5. **Pointer to next sub-step** — close with "paste back" + what closes after this verification

### Reference shape size limits
- **Algorithmic code (functions, loops, conditionals): ≤ ~30 lines per reference shape.** If larger, split the sub-step.
- **Configuration / data declarations (typed dicts, constants, schemas): up to ~80 lines is fine.** A `TICKERS` list, an endpoint catalog, or a `.gitignore` are *data*, not algorithms — showing the full reference shape in one block is appropriate. The user still types it themselves.
- **Files generated by tooling (`pyproject.toml`, `uv.lock`, `.python-version`): show via `cat` output, not type.** Those aren't typed by the user; they're inspected.

The user adapts comments, naming details, and docstrings to their own voice when typing. The user does NOT paste reference shapes verbatim into project files.

### Mandatory annotations alongside reference shapes
For every reference shape larger than a single function call, include a table covering:
- **Style decisions worth understanding** (e.g., "leading underscore = module-private", "keyword-only via `*,`", "`logger.info(...%s...)` not f-string — lazy formatting")
- **Things deliberately absent** (e.g., "we don't pre-create endpoint subdirectories — `save_to_lake` does this lazily", "no `[build-system]` table because we're application mode not library")
- **Why this differs from the handoff doc / common idiom** when it does

### API-cost discipline
Whenever a sub-step would consume free-tier API budget, **state the cost explicitly** before the run command. Example: "⚠ Burns 1 AV call. You're at N/25 used today after this." Track running totals in conversation.

### Verification-first cadence
Prefer logic-only verification (AST inspection, file `grep`, syntax check) before any live run. Once a sub-step is logic-verified, only THEN propose a smoke test with the minimum number of API calls. Conservative live-runs: 2-ticker smoke before 10-ticker full, etc.

### When unsure, ask — never invent
If the user's intent or the API's behavior is unclear, use AskUserQuestion or have the user paste documentation/screenshots. NEVER fabricate API behavior, response shapes, rate limits, or tier policies. If docs aren't readable via WebFetch, have the user paste relevant sections.

## Current Progress (last updated 2026-05-28)

> Operational state (per-branch plan files, machine-local connection details) lives outside this document — see `~/.claude/plans/` and the project's auto-memory. This section is the high-level public-facing log only.

### Completed phases (oldest → newest)
- **dbt scaffold** (PR #1) — `fintech_dbt/` initialized with empty models/macros/tests
- **Planning docs** (PR #2) — early planning artifacts added (later partially removed)
- **Python ingestion scaffold** (PR #3, merged 2026-05-21) — full local ingestion pipeline for Alpha Vantage + FMP into Bronze JSON lake. ~280 lines of production-shaped Python (`config.py` + `utils.py` + `ingest_alpha_vantage.py` + `ingest_fmp.py`) with atomic Bronze writes, JSONL audit logging, `requests.Session` + retry adapter, throttle/empty-list detection, rate-limit pacing, typed endpoint catalogs via `TypedDict`.
- **Handoff doc removal** (PR #4, merged 2026-05-21) — moved `fintech_pipeline_handoff.md` to gitignored `.claude/notes/` (still accessible to Claude, hidden from portfolio readers).
- **CLAUDE.md purification** (PR #5, merged 2026-05-21) — tightened CLAUDE.md prose, relocated operational/connection facts to per-branch plan files + auto-memory, refreshed the Layer ownership table to reflect DLT-based Silver, and added the meta-file exception to LEARNING MODE.
- **ADR practice + retroactive ADRs 0001–0014** (PR #6, merged 2026-05-22) — introduced [MADR](https://adr.github.io/madr/) decision-log convention under `docs/adr/`, including template `0000-template.md` and 14 backfilled ADRs covering every architecturally significant choice through `feat/ingest-scaffold` (medallion ownership, `uv`, application mode, LEARNING MODE, `.gitkeep`, atomic writes + JSONL logs, dotenv secrets, AV downgrade, TICKERS swap, FMP 5-record cap, EDGAR-deferred insiders, Gold star schema, Terraform for IaC).
- **Decision Log section in CLAUDE.md** (PR #7, merged 2026-05-22) — added `## Decision Log` section + per-ADR links from CLAUDE.md so readers entering at the repo root discover the ADR index without spelunking `docs/adr/`.
- **Terraform bootstrap** (PR #8, merged 2026-05-25) — HCP Terraform Free workspace + GitHub OIDC + Databricks + GitHub providers wired end-to-end. 21 resources under management: UC catalogs `bronze` + `silver` + `ingestion`, schemas `bronze.alpha_vantage` + `bronze.fmp`, volumes `ingestion.alpha_vantage.raw_jsons` + `ingestion.fmp.raw_jsons`, SQL Warehouse `Serverless Starter Warehouse` imported drift-free, GitHub branch protection on `main`. ADR-0014 (TF for IaC), ADR-0015 (dbt Cloud Developer API usable; TF deferred), ADR-0016 (Default Storage workaround), ADR-0017 (account-admins principal unavailable) all published in this PR.
- **TF fix-forward: catalog storage_root drift** (PR #9, merged 2026-05-25) — `lifecycle.ignore_changes = [storage_root]` on UC catalogs; Free Edition Default Storage rewrites the field server-side on every apply otherwise.
- **TF fix-forward: UC grants principal** (PR #10, merged 2026-05-25) — pinned grants principal to workspace owner email; `account admins` is not a resolvable principal on Free Edition (ADR-0017).
- **Bronze on Databricks** (PR #11, merged 2026-05-27) — local Bronze JSONs uploaded to UC volumes (`databricks-sdk` Files API; ~108 files across 10 tickers × 11 endpoints); PySpark Autoloader (`cloudFiles` + `.trigger(availableNow=True)`) wired as 11 `databricks_job` × `for_each` in TF, with rescue-mode schema evolution. Includes uploader script, Autoloader `run.py`, ADR-0018 establishing Autoloader as the Bronze engine (supersedes COPY INTO from ADR-0002).
- **TF fix-forward: Autoloader environment_version** (PR #12, merged 2026-05-27) — pinned `databricks_job.environment.spec.environment_version` to `"5"`; Free Edition rejects the provider docs' example `"1"` ("Standard v1 (Unsupported)") and only supports v4/v5 for `spark_python_task`.
- **Defer Alpha Vantage from Bronze** (PR #13, merged 2026-05-28) — removed the AV Autoloader job; AV's `TIME_SERIES_DAILY` response uses a date-keyed STRUCT for `data`, incompatible with the FMP-array `explode(data)` pattern. Bronze now runs 10 streams (FMP only); AV JSONs continue to land in UC and will be consumed at Silver directly (ADR-0019).

### Final TICKERS universe (10)
`AAPL`, `MSFT`, `AMZN`, `META`, `TSLA`, `JPM`, `JNJ`, `NVDA`, `GOOGL`, `PYPL` — chosen across sectors to exercise schema evolution, SCD2 events (META 2018 sector reclassification, JNJ→Kenvue 2023 spinoff, NVDA 2024 split), bank-vs-tech schema enforcement, and no-dividend null handling.

### Final endpoint catalog

Endpoint names below are the canonical **disk + Bronze table** form (matches `FMP_ENDPOINTS[*].name` in [`fintech_datalake/scripts/config.py`](fintech_datalake/scripts/config.py) and Bronze table FQNs `bronze.fmp.<name>`). The API URL path is shown in parentheses where it differs.

- **Alpha Vantage (1 endpoint):** `time_series_daily` (URL: `?function=TIME_SERIES_DAILY`, compact = 100 days) — cross-validation feed for daily prices. Deferred from Bronze per [ADR-0019](docs/adr/0019-alpha-vantage-deferred-from-bronze.md); Silver consumes directly.
- **FMP (10 endpoints, all in Bronze):**
  - `profile` — no allowlist; company snapshot
  - `historical_price_full` (URL: `historical-price-eod/full`) — raw OHLCV
  - `historical_price_adjusted` (URL: `historical-price-eod/dividend-adjusted`) — split/dividend-adjusted OHLCV
  - `income_statement` (URL: `income-statement`) — capped at 5 records/call (see ADR-0011)
  - `balance_sheet` (URL: `balance-sheet-statement`) — capped at 5/call
  - `cash_flow` (URL: `cash-flow-statement`) — capped at 5/call
  - `key_metrics` (URL: `key-metrics`) — capped at 5/call, annual cadence only
  - `earnings`, `dividends`, `splits` — **full history** (ADR-0011 amendment 2026-05-28; the 5-record cap does NOT apply to these three)

FMP is the primary source for daily prices + fundamentals + corporate actions.

### Major architectural decisions
*(See [Decision Log](#decision-log) for the per-decision ADRs with full reasoning.)*

| Decision | Why |
|---|---|
| `uv` for Python deps + lockfile | Reproducibility; PEP 621-native; fast. Application mode, not library. |
| `python-dotenv` + env-var loading | 12-factor secrets; never hardcode keys. |
| Atomic Bronze writes (`.tmp` + rename) | Crash-safety even mid-write. |
| JSONL audit log (`ingestion_log.jsonl`) | O(1) append; jq/pandas-friendly; tail-able. |
| AV → cross-validation only (compact 100 days) | AV's `outputsize=full` moved to premium-only (discovered 2026-05-18); FMP took over as primary daily-price source. |
| TICKERS swap GOOG→GOOGL, BRK-B→PYPL | Both BRK-B and GOOG are outside FMP free-tier's 85-ticker allowlist. GOOGL preserves dual-class narrative; PYPL preserves "no-dividend + corporate-action spinoff" narrative. |
| Fundamentals capped at 5 records per call (4 of 7 endpoints) | FMP free-tier constraint on `income_statement`/`balance_sheet`/`cash_flow`/`key_metrics`; Silver layer handles partial history. `earnings`/`dividends`/`splits` are NOT capped (ADR-0011 amendment 2026-05-28). |
| Insider trades → Phase 3 via SEC EDGAR | FMP's per-symbol insider endpoints are paywalled; SEC EDGAR Form 4 will recover this capability in a future phase. |
| Silver = DLT pipelines | DLT verified available on Free Edition (handoff doc's claim was stale); `dlt.create_auto_cdc_flow(..., stored_as_scd_type=2)` gives native SCD2. |
| Gold star schema (Kimball), 11 tables | 6 facts (`fact_stock_daily`, `fact_earnings_event`, `fact_financial_statement`, `fact_key_metric`, `fact_dividend_event`, `fact_split_event`) + 3 dims (`dim_date`, `dim_company` SCD2, `dim_fiscal_period`) + 2 aggregates (`agg_sector_daily`, `agg_company_monthly`). BI tool target: Tableau Public. |

### Conventions established
- Branch naming: `init/`, `feat/`, `chore/`, `fix/` prefixes
- Merge strategy: squash-and-merge, delete branch after merge
- Python toolchain: `uv` (Astral) for venv + dependency management; lockfile committed
- Secrets: never committed; API keys via env vars; placeholder `.env.example` uses angle-bracket form (`<your-key>`)
- Logging: library modules use `logger = logging.getLogger(__name__)` only; entry-point scripts call `logging.basicConfig(...)` once
- Error handling: `try/except/else` (not `try/except + continue`) so pacing/cleanup always runs
- Atomic writes to Bronze: `.tmp` sibling + `rename` for crash-safety
- JSONL for append-only logs (O(1) append vs O(n²) JSON-array rewrite)
- **Session-pause discipline:** end-of-day, update the `## ⏸ Session pause` marker in the branch's plan file with what's done + resume point
- **Daily-fresh sessions:** start a new Claude Code session each day; resume by reading the branch's plan file. Reasons: dashboard activity attribution; per-turn token cost grows linearly with conversation length

### Free-tier constraints to live with
- AV: 25/day, 5/min, `TIME_SERIES_DAILY?outputsize=full` is premium-only (compact = 100 days only)
- FMP: 250/day, 85-ticker allowlist on most per-symbol endpoints (`profile` exempt), 5-response cap on 4 of 7 fundamentals endpoints (statements + `key_metrics`; `earnings`/`dividends`/`splits` return full history — see ADR-0011 amendment), `key_metrics` annual-only
- Databricks Free Edition: serverless cluster auto-stops after ~10 min idle (~30-60s warm-up); DLT available
- dbt Cloud Developer: ~3,000 model runs/month
- GitHub: unlimited Actions minutes for public repos

### Next phase
1. **`feat/silver-dlt`** — DLT pipelines for CDC + SCD2 via `dlt.create_auto_cdc_flow(stored_as_scd_type=2)`; `@dlt.expect_*` for data quality. AV `time_series_daily` joins here per [ADR-0019](docs/adr/0019-alpha-vantage-deferred-from-bronze.md).
2. **`feat/gold-dbt`** — dbt models for the 11 Gold tables; tests + docs.
3. **`feat/ci-cd`** — GitHub Actions for dbt + lint + docs deploy to GitHub Pages.
4. **Phase 3 (later):** `feat/sec-edgar-insiders` — recover `fact_insider_trade` via SEC EDGAR Form 4.

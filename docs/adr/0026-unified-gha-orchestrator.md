# 0026 — Unified GitHub Actions orchestrator: one scheduled master pipeline chaining ingest → bronze → silver → gold → serve

- **Status:** Accepted
- **Date:** 2026-06-18
- **Deciders:** project owner

## Context

Until this branch, every medallion stage was triggered **independently and by hand** (or by an unrelated event): ingestion ran locally (`uv run python ingest_*.py`), Bronze Autoloader jobs + Silver DLT pipelines were started on-demand from the Databricks UI or ad-hoc REST calls, Gold ran on merge-to-`main` via `prod.yml`, and the BI serving layer ran on its own weekly cron in `bi-refresh.yml`. There was **no single control plane** — nothing guaranteed the stages ran in order, nothing halted downstream work when an upstream stage failed, and a "did the whole pipeline run?" question had no single answer to point at.

The forces in play:

- **Free-tier / no-ops constraint.** The whole project bans paid services and always-on infrastructure. An orchestrator must be serverless — no scheduler daemon to host.
- **GHA-over-Airflow is already locked** (assessment 2026-06-07; see memory `project_orchestration_gha.md` and the CLAUDE.md Next-phase note). GitHub Actions hosts the cron + ephemeral runners with zero always-on cost; Airflow's scheduler is an always-on daemon whose cost is cadence-independent, which breaks the constraint, and at 10-ticker scale it is over-engineering. This ADR **does not re-litigate** that choice — it executes it.
- **Every trigger mechanism already exists and is proven** — the only genuinely unproven piece at design time was firing the **Databricks** Jobs/Pipelines REST APIs from a GHA runner (the dbt Cloud Admin-API trigger was already proven by `prod.yml`, [ADR-0022](0022-cicd-github-actions-dbt-cloud.md)). CP0 verified the Databricks REST triggers work from CI with the existing `DATABRICKS_TOKEN`.
- **Databricks Free Edition runs ~1 serverless workload at a time.** A stage that fans out (Bronze's 11 Autoloader jobs, Silver's source pipelines) cannot trigger them all concurrently — parallel legs queue and time out. This forced a serialization decision (see Decision).
- **Ingest is the only budget-bearing stage.** A scheduled cadence must keep AV (25/day) + FMP (250/day) under their daily caps; a weekly full ingest (~200 FMP / ~20 AV, SEC keyless) fits comfortably.

## Decision

We add a **third, scheduled** GitHub Actions workflow — `.github/workflows/master-pipeline.yml` — as the single orchestration control plane. It does **not** replace `ci.yml`/`prod.yml`; those keep serving the PR/merge dev-loop unchanged.

- **Triggers:** `on: schedule` (cron `0 6 * * 1` — Mondays 06:00 UTC) **plus** `workflow_dispatch` with a `stages` choice input (`ingest-only`, `up-to-bronze`, `up-to-silver`, `up-to-gold`, `full`; default `full`) so the chain can be partially run for testing without burning a full pass. A `concurrency` group (`master-pipeline`, `cancel-in-progress: false`) prevents an overlapping scheduled + manual run.

- **Chain (each stage a job, downstream `needs:` upstream → hard-halt on failure):**
  1. `ingest` — runs `ingest_fmp.py`, `ingest_alpha_vantage.py`, `ingest_sec_edgar.py`, then `upload_bronze_to_uc.py` (Databricks SDK Files API → UC volumes). No SQL warehouse touched.
  2. `bronze` — **matrix over `vars.BRONZE_JOB_IDS`** (the 11 Autoloader jobs), `max-parallel: 1`. Each leg `POST /api/2.1/jobs/run-now`, then polls `GET /api/2.1/jobs/runs/get` until `life_cycle_state` is terminal, and fails the leg if `result_state != SUCCESS`.
  3. `silver-sources` — **matrix over `vars.SILVER_SOURCE_PIPELINE_IDS`**, `max-parallel: 1`. Each leg `POST /api/2.0/pipelines/{id}/updates` with `{"full_refresh": false}`, polls `GET .../updates/{update_id}` until terminal, fails on `state != COMPLETED`.
  4. `silver-dq` — same DLT trigger/poll for `vars.SILVER_DQ_PIPELINE_ID` (the cross-validation + coverage pipeline), gated `needs: silver-sources`.
  5. `gold` — **lifts the proven `prod.yml` pattern verbatim**: `POST` the dbt Cloud Admin API to trigger the "Prod build" Deploy job (`70506183132667`), poll `runs/{id}/` until `status >= 10`, fail on `status != 10`.
  6. `serve` — checks out, runs `serve_to_sheets.py` (Databricks SQL → `gspread`) to land Gold marts in the Google Sheet, `needs: gold`.

- **Concurrency / serialization:** stages run **sequentially across** the chain via `needs:`; **within** the fan-out stages (`bronze`, `silver-sources`) legs run **serially** (`max-parallel: 1`) because Free Edition serverless is ~1-concurrent. `fail-fast: false` on the matrices so one failing leg reports cleanly rather than cancelling siblings mid-flight.

- **IDs + secrets are externalized, not hardcoded.** Job/pipeline IDs come from GitHub Actions **`vars`** (`BRONZE_JOB_IDS`, `SILVER_SOURCE_PIPELINE_IDS`, `SILVER_DQ_PIPELINE_ID`); credentials from **secrets** (`FMP_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_HTTP_PATH`, `DBT_CLOUD_API_TOKEN`, `GOOGLE_SERVICE_ACCOUNT`). `FMP_API_KEY` + `ALPHA_VANTAGE_API_KEY` were added (TF-managed) for this branch.

- **One scheduler, not two.** `bi-refresh.yml`'s weekly cron — identical to the master pipeline's — is **demoted to `workflow_dispatch`-only**, since the master pipeline's `serve` job now owns the scheduled Sheet write. `bi-refresh.yml` survives as a manual escape hatch.

## Considered alternatives

- **Apache Airflow** — rejected: always-on scheduler daemon breaks the free-tier/no-ops constraint; over-engineering at 10-ticker scale. Airflow belongs in a separate, dedicated project. (Decision pre-locked; see memory `project_orchestration_gha.md`.)
- **Keep the scattered per-stage triggers** — rejected: no ordering guarantee, no failure propagation, no single "did it run?" surface.
- **Stop the chain at `gold` and keep `bi-refresh.yml`'s independent cron** — rejected: two schedulers firing at the same time would write the Sheet twice. Demoting one is cleaner than coordinating both.
- **Run Bronze/Silver fan-out legs in parallel (`max-parallel` > 1)** — rejected empirically: Free Edition serverless is ~1-concurrent, so parallel legs queue and time out. Proven by the first true end-to-end run; serialization (`max-parallel: 1`) is the working configuration.
- **A single Databricks Job/DLT-pipeline-of-pipelines doing the whole chain inside Databricks** — rejected: would hide orchestration inside Databricks and orphan the dbt Cloud + Sheets stages, breaking the single-pane, repo-visible-pipeline narrative (same reasoning as [ADR-0022](0022-cicd-github-actions-dbt-cloud.md)).

## Consequences

- **Positive:** One repo-visible control plane (the Actions tab) runs the full medallion flow `ingest → bronze → silver → gold → serve` on a weekly cron, with `needs:`-based hard-halt so a failed stage never lets downstream run on stale/partial data. It **reuses** every existing trigger mechanism (Databricks Jobs/Pipelines APIs, the `prod.yml` dbt Admin-API pattern, `serve_to_sheets.py`) rather than rebuilding them. IDs + secrets are externalized, so TF recreating a resource doesn't require a workflow edit. `workflow_dispatch` + the `stages` input make partial test runs cheap. Proven end-to-end: a `full` dispatch ran green in **24m35s** (ingest 5m4s · bronze 11/11 · silver 5/5 · dq 1m4s · gold 3m21s · serve 40s).
- **Negative / cost:** `max-parallel: 1` serializes the fan-out stages, so wall-clock is dominated by Free-Edition serverless warm-ups stacked end-to-end (~24m total) — acceptable for a weekly batch, but it would not scale to a large ticker universe. `ingest` is the only budget-bearing stage (~200 FMP / ~20 AV per full run); a faster cadence would risk the daily caps. The Databricks trigger logic is inline curl/jq in the workflow (consistent with `prod.yml`) rather than a tested helper module. Each serverless stage pays a cold-start the poll loops must absorb.
- **Follow-ups required:** none blocking. A future optimization could probe `max-parallel: 2` if Free Edition ever tolerates 2 concurrent serverless workloads. The first true end-to-end run also surfaced two **pre-existing, non-orchestration** data defects (Silver `company_scd2` churn from an untracked-but-volatile `description` column, and the `agg_company_monthly` grain grouping by the SCD2 surrogate `company_key`) — both fixed in PR #40, independent of this orchestrator; recorded here for honesty because the orchestrator's hard-halt is what exposed them.

## References

- [ADR-0022](0022-cicd-github-actions-dbt-cloud.md) — the dbt Cloud Admin-API trigger + poll + TF-secrets pattern this lifts for the `gold` stage; `ci.yml`/`prod.yml` remain the untouched PR/merge dev-loop.
- [ADR-0025](0025-bi-tableau-via-sheets-serving-layer.md) — `serve_to_sheets.py` + `bi-refresh.yml` (the `serve` stage + the cron-demotion target).
- [ADR-0018](0018-bronze-pyspark-autoloader-supersedes-copy-into.md) — Bronze Autoloader jobs the `bronze` stage triggers; `allowOverwrites=false` re-upload idempotency.
- [ADR-0020](0020-silver-dq-observability-schema.md) — the `silver.dq` pipeline the `silver-dq` stage runs.
- Memory `project_orchestration_gha.md` — the GHA-over-Airflow decision + reasoning (locked; not re-litigated here).
- Memory `project_free_edition_serverless_concurrency.md` — the ~1-concurrency fact forcing `max-parallel: 1`.
- `.github/workflows/master-pipeline.yml` — the implementing workflow; `.github/workflows/bi-refresh.yml` — cron demoted to dispatch-only.
- Plan file `~/.claude/plans/feat-gha-orchestrator.md` — CP0–CP5 decision + verification trail.

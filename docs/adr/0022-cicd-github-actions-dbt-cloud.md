# 0022 — CI/CD via GitHub Actions: dbt Cloud CLI Slim-CI on PR, Admin-API job-trigger for CD, docs → Pages

- **Status:** Accepted
- **Date:** 2026-06-03
- **Deciders:** project owner

## Context

`feat/ci-cd` wires end-to-end CI/CD around the existing UI-managed dbt Cloud project (dbt Cloud TF management stays deferred per [ADR-0015](0015-dbt-cloud-developer-api-usable.md)), per the CLAUDE.md `## CI/CD Conventions`: PR → checks; merge → prod build + docs to GitHub Pages.

One technical fact dominates the design and overturned the branch's initial plan: **the dbt Cloud CLI executes only in the project's Development environment, with the developer's personal credentials → `workspace.dbt_praj`. It cannot target a Deployment (Production) environment.** There is no `--target prod` for the Cloud CLI, and a project has exactly one Development environment. This was verified against dbt's own docs ([CLI install](https://docs.getdbt.com/docs/cloud/cloud-cli-installation), [dbt environments](https://docs.getdbt.com/docs/dbt-cloud-environments)) and observed empirically: the PR Slim-CI builds land in `dbt_praj`, never `gold.marts`.

The consequence: `gold.marts` (the Production catalog.schema, owned by the `Production` Deployment environment + its credentials, [ADR-0021](0021-gold-implementation-refinements.md)) is reachable **only by a dbt Cloud Job**. So the two halves of CI/CD have fundamentally different mechanisms — the PR check can use the CLI (it writes to dev, which is what Slim CI wants), but the production build on merge cannot.

Secondary forces:

- **Slim CI deferral** (`state:modified+`) needs a prod `manifest.json` to compare against. The dbt Cloud CLI auto-defers + auto-resolves state to the environment flagged **Production**, so no `--state`/`--defer` flags or manifest plumbing are needed once a Production env has a successful run.
- **Free-tier auth ceiling.** The dbt Cloud Developer plan exposes only two service-token permission sets — **Account Admin** and **Read-Only**; the granular **Job Runner** / **Job Admin** roles are Team-plan-and-up. A Read-Only token cannot trigger a job (triggering is a write → `POST .../run/`).
- **GitHub Pages is not cleanly Terraformable here.** The `integrations/github` provider has no standalone Pages resource; Pages is only a `pages {}` block *inside* a `github_repository` resource. This repo is not TF-managed as a `github_repository` (TF only references it by name for branch protection + secrets, see [ADR-0014](0014-terraform-for-iac.md)), so TF-managing Pages would require importing the entire repository (~30 settings → perpetual drift reconciliation).
- **Cost discipline.** Each production `dbt build` consumes dbt Cloud model-run budget (~3,000/month). A merge that touches only docs/ADRs/CI files should not spin up the warehouse.
- **Lint scope.** `pre-commit` + `sqlfluff` were attempted and deliberately backed out of this branch (sqlfluff cannot resolve namespaced dbt *package* macros under the `jinja` templater without dbt-core; rule-chasing ate time). Lint is deferred to a dedicated future effort, not a checkpoint here.

## Decision

CI/CD runs entirely through **GitHub Actions**, with dbt executing in dbt Cloud. Two workflows:

1. **PR — `.github/workflows/ci.yml`** (`on: pull_request: [main]`): install the pinned dbt Cloud CLI, configure it from the `DBT_CLOUD_CONFIG` secret, and run `dbt build --select state:modified+`. The Cloud CLI **auto-defers + auto-resolves state** against the Production environment's last successful run (no `--state`/`--defer` flags). Builds land in the dev schema (`workspace.dbt_praj`). **No lint job.**

2. **Merge — `.github/workflows/prod.yml`** (`on: push: [main]` path-filtered to `fintech_dbt/**`, plus `workflow_dispatch`): GitHub Actions **triggers the dbt Cloud "Prod build" Deploy job** (job `70506183132667`, Production env → `gold.marts`) via the **dbt Cloud Admin API v2** — `POST /api/v2/accounts/{acct}/jobs/{job}/run/` with `Authorization: Token <service-token>` — then **polls** `GET .../runs/{run}/` until `.data.status ≥ 10` (terminal), failing the workflow on any status ≠ 10. It then **downloads** the run's docs artifacts (`manifest.json`, `catalog.json`, `index.html`) and **deploys** them to GitHub Pages via `actions/upload-pages-artifact` + `actions/deploy-pages` (a second `deploy` job gated on `needs: prod-build`). The "Prod build" job has **Generate docs on run** enabled.

Supporting decisions:

- **Auth → dbt Cloud Service Token, `Account Admin` scope**, stored as the GitHub secret `DBT_CLOUD_API_TOKEN`. Account Admin is broader than ideal, but it is the only Developer-plan service-token role that can trigger a job.
- **Production-build mechanism is the API-triggered Deploy job, not a CLI build.** GitHub Actions orchestrates (trigger + poll + artifact handling), keeping the whole pipeline visible in the repo's Actions tab; the dbt execution for prod necessarily runs as the Cloud Job.
- **Path filter `paths: ['fintech_dbt/**']`** on the merge trigger: merges touching only docs/ADRs/`.github`/CLAUDE.md do not fire a production build.
- **GitHub Pages enabled via the GitHub UI** (Settings → Pages → Source: GitHub Actions), recorded here as a deliberate non-Terraform exception in the spirit of [ADR-0016](0016-free-edition-default-storage-workaround.md)/[ADR-0017](0017-free-edition-account-admins-principal-unavailable.md).

## Considered alternatives

- **Production build via dbt Cloud CLI in Actions** (the branch's original plan) — rejected: the CLI provably cannot write to `gold.marts`; it always runs as the Development environment.
- **dbt Cloud native CI / Merge jobs** (GitHub-app-triggered, which *are* available on this plan) — rejected: execution would be hidden inside dbt Cloud, breaking the single-pane, repo-visible-pipeline portfolio narrative. Actions stays the orchestrator.
- **dbt-core + dbt-databricks directly in Actions for the prod build** — rejected: reintroduces the deliberately-removed local dbt-core, splits the toolchain, and orphans the dbt Cloud Production env created for this purpose.
- **Read-Only or Job-Runner service token** — Read-Only rejected (cannot trigger a write/run); Job-Runner unavailable below the Team plan. Account Admin is the forced minimum.
- **Pages enablement via Terraform** — rejected: no standalone Pages resource exists; the only path is importing the whole repository into TF state (drift-prone, [ADR-0016] territory) for a single set-and-forget toggle.
- **`actions/configure-pages` with `enablement: true`** — rejected: it requires a credential other than `GITHUB_TOKEN` (a PAT/App with pages-write), adding a long-lived secret to manage.
- **`pre-commit` + `sqlfluff` lint job in PR CI** — deferred out of this branch entirely (future `feat/lint-precommit`): sqlfluff's `jinja` templater can't resolve namespaced package macros (`dbt_utils.*`, `dbt_date.*`) without dbt-core; not worth the weight or the rule-chasing now.

## Consequences

- **Positive:** One repo-visible pipeline (Actions tab) covers PR → prod → docs. The CD workflow reuses the existing CP1 Deploy job rather than rebuilding prod logic. The path filter keeps merge cost proportional to dbt change. Slim CI defers to the Production manifest automatically, so PR runs stay small. A broken prod build surfaces as a red ❌ on `main` (poll fails on status ≠ 10) and `deploy` is gated on it, so a failed build never publishes stale docs.
- **Negative / cost:** The production *execution* is not in Actions — Actions only triggers + polls + ships artifacts; the build runs as the dbt Cloud Job. The service token is over-privileged (Account Admin) because the free tier offers no finer role. Pages enablement is click-ops, not IaC. Two secrets (`DBT_CLOUD_CONFIG`, `DBT_CLOUD_API_TOKEN`) are currently UI-set, not Terraform-managed like `DATABRICKS_*`. No lint gate exists on PRs yet.
- **Follow-ups required:** `pre-commit` + `sqlfluff` → future `feat/lint-precommit`. Backfill `DBT_CLOUD_CONFIG` + `DBT_CLOUD_API_TOKEN` into Terraform `github_actions_secret` for IaC consistency. Bump `actions/checkout@v4` → `@v5` (Node20 deprecation warning). If the dbt Cloud plan is ever upgraded, replace the Account-Admin service token with a least-privilege Job-Runner token. Environment-tier rationale (2-tier, no UAT) is recorded separately in [ADR-0023](0023-two-tier-dbt-environments.md).

## References

- [ADR-0014](0014-terraform-for-iac.md) — existing GitHub provider: branch protection + TF-managed `DATABRICKS_*` secrets (the secrets-via-TF pattern this branch follows for the future backfill).
- [ADR-0015](0015-dbt-cloud-developer-api-usable.md) — dbt Cloud stays UI-managed; TF management deferred.
- [ADR-0016](0016-free-edition-default-storage-workaround.md), [ADR-0017](0017-free-edition-account-admins-principal-unavailable.md) — prior free-tier UI-workaround precedents (Pages-via-UI follows this pattern).
- [ADR-0021](0021-gold-implementation-refinements.md) — `gold.marts` prod routing (deferred to this branch).
- [ADR-0023](0023-two-tier-dbt-environments.md) — the 2-tier environment model this CI/CD targets.
- dbt Cloud API v2 — [trigger/poll reference](https://docs.getdbt.com/dbt-cloud/api-v2); status codes 10/20/30 = success/error/cancelled.
- `.github/workflows/ci.yml`, `.github/workflows/prod.yml` — the implementing workflows.
- Plan file `~/.claude/plans/feat-ci-cd.md` — CP0–CP7 decision + verification trail.

# 0023 — Two-tier dbt environment model (dev → prod, no UAT)

- **Status:** Accepted
- **Date:** 2026-06-03
- **Deciders:** project owner

## Context

Wiring CI/CD (`feat/ci-cd`, [ADR-0022](0022-cicd-github-actions-dbt-cloud.md)) forced an explicit decision about how many environment tiers the dbt project promotes through. The textbook enterprise shape is three tiers — dev → UAT/staging → prod — with a human acceptance gate before production. Several forces argue against importing that shape wholesale here:

- **Solo portfolio project.** There is no acceptance audience: no separate QA team, no business stakeholders signing off in a staging environment. The "U" in UAT (User Acceptance) has no user.
- **The PR + Slim-CI gate already is the pre-prod check.** Every change runs `dbt build --select state:modified+` against real data (deferring to the Production manifest) on its PR before merge. That green run is the gate a UAT tier would otherwise provide.
- **Identical upstream data.** Dev, a hypothetical UAT, and prod would all read the *same* `silver.fmp` tables. A UAT build would be byte-for-byte identical to the prod build — it would validate nothing that the PR Slim-CI run did not already validate. It would be cargo-cult staging.
- **dbt Cloud Developer-plan limits.** The plan allows exactly one Development environment and caps deployment environments tightly (1 seat, ~3,000 model-runs/month). A third environment spends budget and complexity for no acceptance value.

## Decision

We run **two dbt environments**:

1. **Development** (dbt Cloud Development env) → catalog/schema **`workspace.dbt_praj`**. Used by the Cloud IDE/CLI and by PR Slim-CI builds (which land in the dev schema).
2. **Production** (dbt Cloud Deployment env, flagged Production) → **`gold.marts`**. Built by the "Prod build" Deploy job, triggered on merge to `main` ([ADR-0022](0022-cicd-github-actions-dbt-cloud.md)).

PR Slim-CI builds are the ephemeral pre-prod stage; they execute in the dev environment's schema and are superseded by each run. **There is no UAT/staging tier.**

## Considered alternatives

- **Three tiers (dev → `gold_uat` → prod)** with a 3rd dbt Cloud environment and a manual-approval promote step — rejected: no acceptance audience to use UAT; it would read identical `silver.fmp` data and produce a build byte-identical to prod (validates nothing new); it spends a scarce Developer-plan environment slot + model-run budget; the PR/Slim-CI green is already the pre-prod gate.
- **Single tier (build straight to prod, no dev isolation)** — rejected: developers and PR checks would write to `gold.marts`, contaminating production with in-progress work and breaking the "prod is the source of truth" guarantee. The dev/prod split is the minimum defensible separation.

## Consequences

- **Positive:** Minimal, defensible separation (prod is isolated and credential-gated; dev/PR work never touches `gold.marts`). Fits the Developer-plan limits with room to spare. The 2-tier choice reads as a deliberate, reasoned engineering judgment in review — not an oversight — precisely because the 3-tier option was considered and rejected on stated grounds.
- **Negative / cost:** No human acceptance gate between merge and production — a change that passes Slim CI but is semantically wrong reaches `gold.marts` on merge (mitigated: prod build failure shows red on `main`, docs deploy is gated on a successful build, and the data is non-critical portfolio data). PR Slim-CI builds share the dev schema, so concurrent PRs could interleave objects there (acceptable for a single-author project).
- **Follow-ups required:** If this project ever gains collaborators or a real acceptance audience, revisit by adding a UAT deployment environment (`gold_uat`) + a manual-approval promote — the 2-tier model is a floor, not a ceiling. A dedicated PR-CI environment (separate schema) could replace the shared-dev-schema arrangement if PR interleaving becomes a problem.

## References

- [ADR-0022](0022-cicd-github-actions-dbt-cloud.md) — the CI/CD architecture these environments serve.
- [ADR-0021](0021-gold-implementation-refinements.md) — `gold.marts` prod routing.
- [ADR-0015](0015-dbt-cloud-developer-api-usable.md) — dbt Cloud Developer-plan constraints.
- Plan file `~/.claude/plans/feat-ci-cd.md` — environment-tier decision (locked 2026-06-01 via AskUserQuestion).

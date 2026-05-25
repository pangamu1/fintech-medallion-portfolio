# 0015 — dbt Cloud Developer-plan API is usable; dbt Cloud TF management deferred to dedicated branch

- **Status:** Accepted
- **Date:** 2026-05-25
- **Deciders:** project owner

## Context

[ADR-0014](0014-terraform-for-iac.md) listed three feasibility spikes to run inside `feat/terraform-bootstrap` before committing to scope. Spike 2 asked: *can the `dbt-labs/dbtcloud` Terraform provider authenticate and read resources on a Developer-plan account?* The working assumption was that it could not — dbt Labs typically gates API access behind Team / Enterprise tiers, and the plan documented "likely fails; drop from scope" as the expected outcome.

Spike 2 was executed on 2026-05-25 in an isolated `/tmp/spike2-dbtcloud-provider/` directory with local state backend (same pattern as Spike 1). Credentials were supplied via `DBT_CLOUD_*` environment variables sourced from a personal access token generated in the dbt Cloud UI and the cell-based account host (`https://hf168.us1.dbt.com/api`). The probe was a `data "dbtcloud_project"` lookup of an existing `FinTech_Analytics` project (id `70506183132573`).

The probe **succeeded**: `terraform plan` read the data source in ~1s and surfaced the project name as a Terraform output. Authentication, REST traffic to `us1.dbt.com/api`, and data-source decoding all work end-to-end on the Developer plan.

This contradicts the working assumption in ADR-0014. A scope question reopens: bring dbt Cloud under TF management in `feat/terraform-bootstrap`, or defer to a dedicated branch?

## Decision

**Defer** dbt Cloud Terraform management to a dedicated future branch (working name `feat/dbtcloud-terraform`, scope to be defined when that branch opens). Reasons:

1. `feat/terraform-bootstrap` is already a substantial PR (5 commits, ~20 Databricks + GitHub resources). Adding dbt Cloud resources would inflate its scope and obscure the bootstrap narrative.
2. dbt Cloud TF management is a logically distinct concern (project / environments / repository link / job orchestration) from Databricks workspace provisioning. A dedicated branch produces a cleaner ADR / commit / review story.
3. The Spike 2 finding itself — that the provider works — is the load-bearing decision; the *when* of adopting it is reversible. Recording the finding now in this ADR ensures the discovery doesn't get lost.

The `dbt-labs/dbtcloud` provider is **not** added to `terraform/providers.tf` in this branch. No dbt Cloud variables are wired into HCP workspace state.

## Considered alternatives

- **Add minimal dbt Cloud scaffold to `feat/terraform-bootstrap`** — rejected. Even a single `data "dbtcloud_project"` lookup would require declaring the provider, pinning a version, plumbing four new HCP workspace variables (`dbt_cloud_account_id`, `dbt_cloud_token`, `dbt_cloud_host_url`, plus a project reference), and updating ADR-0014's "Out of scope" wording. Cost > value for a read-only probe that's already been satisfied by the spike.
- **Fully manage dbt Cloud in `feat/terraform-bootstrap`** — rejected. Bringing project / environments (dev + prod) / repository link / baseline job under TF in this branch would roughly double its scope and entangle two unrelated decisions in one PR. Worse, the right design for dbt Cloud environments depends on how `feat/gold-dbt` evolves, which hasn't been written yet — premature.
- **Skip the ADR; just note the finding in the plan file** — rejected. Plan files live outside the repo (`~/.claude/plans/`); the discovery would not survive into the public portfolio narrative. ADRs are append-only durable history; the spike outcome belongs in that record.

## Consequences

- **Positive:** Scope of `feat/terraform-bootstrap` stays focused on Databricks + GitHub. The Spike 2 finding is durably recorded — a future contributor (or future-me) reading `docs/adr/` chronologically sees that dbt Cloud TF management is *capable* but *intentionally deferred*. The dedicated branch can design dbt Cloud environments alongside the actual dbt project structure in `feat/gold-dbt`.
- **Negative / cost:** A future branch is required to realize the dbt-labs/dbtcloud capability. Until then, dbt Cloud project / environment / job configuration remains clickops, with the usual drift / non-reproducibility cost.
- **Follow-ups required:** Open `feat/dbtcloud-terraform` (or fold into `feat/gold-dbt`) after the Gold dbt models are designed. That branch's scope: declare provider, plumb HCP variables, bring `dbtcloud_project`, `dbtcloud_environment` (dev + prod), `dbtcloud_repository` link, and a baseline `dbtcloud_job` under TF management. Likely a small superseding ADR at that point to confirm the deferred adoption is realized.

## References

- [ADR-0014](0014-terraform-for-iac.md) — original IaC decision; flagged Spike 2 as a feasibility unknown
- `dbt-labs/dbtcloud` Terraform provider — https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest
- Plan file `~/.claude/plans/feat-terraform-bootstrap.md` — Spike 2 section in `## Pre-implementation feasibility spikes` and `### CP10` checkpoint
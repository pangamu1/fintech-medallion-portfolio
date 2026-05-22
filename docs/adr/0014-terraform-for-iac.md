# 0014 — Terraform for infrastructure as code (HCP Terraform Free + Databricks + GitHub providers)

- **Status:** Accepted
- **Date:** 2026-05-22 (decision dated 2026-05-16; implementation deferred)
- **Deciders:** project owner

## Context

Databricks resources (Unity Catalog catalogs, schemas, volumes, SQL endpoints, DLT pipelines, grants) and GitHub repository configuration (branch protection, Actions secrets) all need to be created and kept consistent. Manual clickops is the obvious bad option — non-reproducible, no review, no diff history. The two real candidates are Terraform and Pulumi.

This is a portfolio project, so the IaC choice is also a portfolio signal: "real Databricks shops manage their workspaces with Terraform" is a credible statement we want to demonstrate. The `databricks/databricks` Terraform provider is maintained by Databricks themselves, which makes Terraform the natural pick at the time of this decision (2026-05-16).

Free-tier constraint: we need a remote-state backend that doesn't cost money. HashiCorp's HCP Terraform Free tier (formerly Terraform Cloud) provides encrypted remote state, run history, and a secrets vault at no cost for our scale (single workspace, few resources).

Decision is made *now* but implementation is deferred to a dedicated branch (`feat/terraform-bootstrap`) that runs after this PR. There's nothing to manage yet beyond the workspace itself (which TF can't manage on Free Edition — it's signup-only); the natural insertion point is between "local ingestion works" and "Bronze tables exist."

## Decision

Adopt **Terraform** for infrastructure as code, with:

- **Backend:** HCP Terraform Free tier — remote state, run history, secrets vault.
- **Databricks provider** (`databricks/databricks`) managing: `databricks_catalog` (bronze/silver/gold), `databricks_schema` per catalog, `databricks_volume` for Bronze-JSON uploads, `databricks_sql_endpoint` (imported from the existing manually-created warehouse, not recreated), `databricks_grant` for permissions, `databricks_pipeline` for DLT pipeline scaffolds.
- **GitHub provider** (`integrations/github`) managing: `github_actions_secret` (DATABRICKS_TOKEN), `github_branch_protection` (require PR review + status checks on `main`).

Out of scope for the bootstrap: `dbt-labs/dbtcloud` provider (Developer-plan API access is uncertain — needs a feasibility spike before commitment), Databricks notebooks (managed via git, not TF), and users/groups (single-user workspace).

`terraform.tfstate*` files are gitignored even with remote backend, because local backups can drop a state file in the working directory during plan/apply.

## Considered alternatives

- **Pulumi** — rejected. Excellent tool, but the Databricks provider community is smaller, and the portfolio audience is more likely to read Terraform fluently than Pulumi. Pulumi's "real programming language" advantage doesn't pay back for our resource count.
- **AWS CDK / CDKTF** — rejected. CDK has no Databricks support; CDKTF (CDK for Terraform) adds a transpilation layer with no clear benefit at our scale.
- **Bash + Databricks CLI scripts** — rejected. No state tracking; deletes and renames are error-prone.
- **Databricks SDK Python scripts** — rejected for the same reason as bash; we'd be reinventing TF's state-tracking poorly.
- **Manual clickops with documentation** — rejected. Non-reproducible; no diff history; doesn't meet the portfolio bar.
- **Local-only Terraform state (no remote backend)** — rejected. State on developer laptop is a single point of failure; HCP Free is free, encrypted, and gives a real-org-grade backend.

## Considered for the dbt Cloud provider (deferred)

The `dbt-labs/dbtcloud` Terraform provider exists, but Developer-plan API access is uncertain. Feasibility spike planned in `feat/terraform-bootstrap`: if the API is accessible, manage dbt Cloud jobs/environments via TF; if not, document the manual setup and revisit if dbt Labs opens the API on Developer.

## Consequences

- **Positive:** Reviewer sees `terraform/` directory and immediately recognizes a credible production pattern. Infrastructure changes go through PR review. State history is preserved in HCP. Branch protection on `main` is enforced declaratively — no "I'll set it up manually" drift.
- **Negative / cost:** Terraform learning curve (HCL syntax, provider conventions, state lifecycle, import workflows). HCP Free tier has limits we should confirm don't bite at our scale (resource count, run count/month). The Databricks workspace itself isn't TF-managed on Free Edition — it's a manual signup that TF then attaches to.
- **Follow-ups required:** `feat/terraform-bootstrap` branch implements the bootstrap. Feasibility spikes (before merge): (1) `databricks_pipeline` creation on Free Edition; (2) `dbt-labs/dbtcloud` provider with Developer token; (3) Free Edition secret-scope count limits. Add `.terraform/`, `*.tfstate`, `*.tfstate.backup` to root `.gitignore` in the bootstrap PR.

## References

- HCP Terraform Free tier — https://www.hashicorp.com/products/terraform/pricing
- `databricks/databricks` Terraform provider — https://registry.terraform.io/providers/databricks/databricks/latest
- `integrations/github` Terraform provider — https://registry.terraform.io/providers/integrations/github/latest
- Plan file `~/.claude/plans/resuming-feat-ingest-scaffold-work-on-shimmering-kazoo.md` "Parked-3" section — original 2026-05-16 decision notes

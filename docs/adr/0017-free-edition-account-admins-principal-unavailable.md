# 0017 — Databricks Free Edition: `account admins` not a resolvable principal; UC grants pinned to workspace owner email

- **Status:** Accepted
- **Date:** 2026-05-25
- **Deciders:** project owner
- **Supersedes:** none. **Refines:** [ADR-0014](0014-terraform-for-iac.md) (scope of Databricks provider grants in `feat/terraform-bootstrap`); related to [ADR-0016](0016-free-edition-default-storage-workaround.md) (second Free Edition limitation discovered in the same apply cycle).

## Context

The first successful Terraform apply on `main` (after the ADR-0016 catalog workaround) created 16 of 20 declared resources but errored on all four `databricks_grant.*_account_admins` resources with:

```
cannot create grant: Could not find principal with name account admins.
```

The grants were declared with `principal = "account admins"` — the canonical name of the built-in account-admins group on Databricks paid tiers, where it is a first-class group that can be granted UC privileges directly.

On Databricks Free Edition, this group is **not exposed to the catalog grant API**. The workspace effectively has one user (the account owner), who is the de-facto account admin but is not surfaced through the same group abstraction.

There is no Free Edition equivalent name we can substitute (e.g., `"users"`, `"account users"`) that semantically maps to "account admins."

## Decision

Grant resources use the **workspace owner's email** (`piruthviraj5@outlook.com`) as the principal:

```hcl
resource "databricks_grant" "ingestion_account_admins" {
  catalog    = databricks_catalog.ingestion.name
  principal  = "piruthviraj5@outlook.com"
  privileges = ["ALL_PRIVILEGES"]
}
```

An inline comment at the top of `terraform/grants.tf` cites this ADR so a reader encountering the hardcoded email immediately understands why a group name isn't used.

The resource label (`*_account_admins`) is **retained** rather than renamed to `*_owner` because the semantic intent — granting the account-admin-equivalent permission — is preserved. The principal value is the Free Edition implementation detail; the resource label is the intent.

## Considered alternatives

- **`principal = "users"`** (built-in account users group). Rejected. Semantically wrong (users ≠ admins) and may suffer the same Free Edition exposure issue. We did not empirically probe this — switching to the email satisfied the intent without further experimentation.
- **Drop `grants.tf` entirely.** Rejected. On a single-user workspace the owner has implicit `ALL_PRIVILEGES`, so the grants are functionally cosmetic — but they document the project's intended UC privilege posture. Future contributors (or paid-tier migration) need that artifact.
- **Look up the principal dynamically via `data "databricks_current_user"`.** Rejected. Adds indirection for a value that will not change in practice on this single-user workspace. The literal is more readable and the inline comment + this ADR document the brittleness for the rare case it ever does change.
- **Use service principal IDs.** Rejected. Free Edition does not expose the service-principal management UI the way paid tiers do; no clean path to create + reference one.

## Consequences

- **Positive:** UC grants are declarative and TF-managed end-to-end. The grants block remains as a portfolio artifact demonstrating UC privilege management. Switching to paid tier later means changing four `principal` values (and updating this ADR + the inline comment) — a mechanical, small-scope migration.
- **Negative / cost:** The email is hardcoded in `terraform/grants.tf` and committed to a public repo. The email is already public (it's the GitHub commit author, the dbt Cloud account holder, etc.), so this is not a meaningful exposure increase — but it is *one more place* the email appears, and a malicious actor reading the repo learns the workspace owner. Acceptable for a portfolio repo; would be reconsidered for an internal/enterprise repo.
- The `lifecycle` of the grants is now tied to the workspace owner's identity. If the owner's email ever changes (account migration, name change, etc.), the grants must be updated and re-applied.
- **Follow-ups required:** When `databricks_grant` resources are added in future branches, this same constraint applies — use the workspace owner email until Free Edition exposes group principals. If Databricks publishes a Free-Edition-compatible group name or a `data "databricks_account_admin"` data source, supersede this ADR by re-pointing the principal.

## References

- [ADR-0014](0014-terraform-for-iac.md) — original Terraform-for-IaC decision; grants scope.
- [ADR-0016](0016-free-edition-default-storage-workaround.md) — sibling Free Edition limitation (catalog Default Storage).
- `databricks_grant` provider docs — https://registry.terraform.io/providers/databricks/databricks/latest/docs/resources/grant
- Plan file `~/.claude/plans/feat-terraform-bootstrap.md` — apply error log and triage discussion in the 2026-05-25 session resume notes.

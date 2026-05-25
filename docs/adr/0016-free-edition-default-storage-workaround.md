# 0016 — Databricks Free Edition Default Storage; UC catalogs managed via UI + TF import, not TF create

- **Status:** Accepted
- **Date:** 2026-05-25
- **Deciders:** project owner
- **Supersedes:** none. **Refines:** [ADR-0014](0014-terraform-for-iac.md) (scope of Databricks provider in `feat/terraform-bootstrap`).

## Context

The Terraform apply for [ADR-0014](0014-terraform-for-iac.md)'s catalog scope failed on `databricks_catalog` resource creation against a Databricks Free Edition workspace. The provider returned:

```
cannot create catalog: Metastore storage root URL does not exist.
Default Storage is enabled in your account. You can use the UI to create
a new catalog using Default Storage, or please provide a storage location
for the catalog (for example 'CREATE CATALOG myCatalog MANAGED LOCATION
'<location-path>').
```

Free Edition does not expose a traditional metastore-level `storage_root`. Instead, the account has *Default Storage* — a workspace-managed S3 bucket that Databricks transparently allocates to catalogs at create time. The Databricks UI knows about Default Storage and calls a code path that uses it implicitly; the public API (which the `databricks_catalog` Terraform resource calls) does not — it looks for a metastore `storage_root`, finds none, and refuses to create.

The provider's `storage_root` attribute is documented as "(Optional if `storage_root` is specified for the metastore)" — meaning it falls back to the metastore root, which Free Edition simply doesn't have in the traditional sense. There is no Terraform attribute to opt into Default Storage explicitly.

Free Edition users therefore cannot create UC catalogs through Terraform at all.

## Decision

Catalogs are **created in the Databricks UI** (which uses Default Storage automatically) and then **imported** into Terraform state. Each `databricks_catalog` resource carries a `lifecycle { ignore_changes = [storage_root] }` block so that subsequent plans ignore the drift between the (UI-assigned, in-state) S3 path and the (absent in HCL) `storage_root` value.

Concretely:

```hcl
resource "databricks_catalog" "ingestion" {
  name    = "ingestion"
  comment = "Raw uploaded source files (volumes only). Boundary between Python ingestion and Databricks."

  lifecycle {
    ignore_changes = [storage_root]
  }
}
```

Workflow per catalog:

1. Create the catalog in Databricks UI (Catalog Explorer → Create catalog → accept Default Storage).
2. `terraform import databricks_catalog.<name> <name>` against HCP-managed state (run locally per CP5 detour pattern; HCP VCS-driven workspaces block CLI applies but allow imports).
3. `terraform plan` confirms in-place updates only (typically `comment` — UI catalogs are created without one).

All non-catalog UC resources (`databricks_schema`, `databricks_volume`, `databricks_grant`, `databricks_pipeline`) continue to be **created** via Terraform without issue — the Default Storage limitation is specific to catalog creation, not to children of an existing catalog.

## Considered alternatives

- **Specify `storage_root` explicitly per catalog in HCL.** Rejected. Would require hardcoding the workspace-internal S3 path (e.g., `s3://dbstorage-prod-gixwb/uc/.../...`), which is not a stable contract from Databricks. Path is opaque to users on Free Edition (no S3 access).
- **Drop catalog resources from Terraform; put schemas/volumes/grants under the built-in `workspace` catalog.** Rejected. Loses the medallion-catalog separation (ingestion / bronze / silver / gold) that organizes the project's data flow. The catalogs are the load-bearing namespace in [ADR-0002](0002-medallion-layer-ownership.md); collapsing them would obscure layer ownership.
- **Upgrade to a paid Databricks tier with a real metastore.** Rejected. Violates the free-tier-only constraint that frames the entire project.
- **Accept forced replacement on `storage_root` drift, hope Default Storage reassigns successfully.** Rejected. Replacement = destroy + create, and create fails with the same Default Storage error — infinite loop.

## Consequences

- **Positive:** Catalogs are still declared in Terraform, so the medallion structure remains visible in `terraform/catalogs.tf` and surfaces in `terraform plan` / `terraform graph` output. Schemas / volumes / grants / pipelines under those catalogs are fully TF-managed in the normal create-on-apply path. Reviewer reading the repo sees one `lifecycle` block per catalog with a clear ADR explaining why.
- **Negative / cost:** Each new catalog requires a manual UI step (create) followed by a CLI step (import) before subsequent TF apply can pick up changes. Not reproducible from a clean state with `terraform apply` alone — a fresh contributor cloning the repo cannot stand up the workspace without running the UI-create + import dance documented in this ADR. The `lifecycle { ignore_changes = [storage_root] }` block also masks any future legitimate drift on `storage_root` (e.g., if Databricks re-locates a catalog) — acceptable trade-off given Free Edition constraints.
- **Follow-ups required:** When `databricks_catalog` resources are added in future branches, this workflow applies. If Databricks publishes a `default_storage = true` attribute on `databricks_catalog` (or equivalent), supersede this ADR by removing the `lifecycle` blocks and the UI-create step.

## References

- [ADR-0014](0014-terraform-for-iac.md) — original Terraform-for-IaC decision; catalog scope.
- [ADR-0002](0002-medallion-layer-ownership.md) — medallion architecture; load-bearing role of the 4 catalogs.
- `databricks_catalog` provider docs — https://registry.terraform.io/providers/databricks/databricks/latest/docs/resources/catalog
- Plan file `~/.claude/plans/feat-terraform-bootstrap.md` — apply error log and triage discussion in the 2026-05-25 session pause marker.

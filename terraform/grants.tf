# Principal pinned to the workspace owner's email rather than the canonical
# "account admins" group: on Databricks Free Edition the built-in account-
# admins group is not exposed to the catalog grant API. See ADR-0017.

resource "databricks_grant" "ingestion_account_admins" {
  catalog    = databricks_catalog.ingestion.name
  principal  = "piruthviraj5@outlook.com"
  privileges = ["ALL_PRIVILEGES"]
}

resource "databricks_grant" "bronze_account_admins" {
  catalog    = databricks_catalog.bronze.name
  principal  = "piruthviraj5@outlook.com"
  privileges = ["ALL_PRIVILEGES"]
}

resource "databricks_grant" "silver_account_admins" {
  catalog    = databricks_catalog.silver.name
  principal  = "piruthviraj5@outlook.com"
  privileges = ["ALL_PRIVILEGES"]
}

resource "databricks_grant" "gold_account_admins" {
  catalog    = databricks_catalog.gold.name
  principal  = "piruthviraj5@outlook.com"
  privileges = ["ALL_PRIVILEGES"]
}

resource "databricks_grant" "ingestion_account_admins" {
  catalog    = databricks_catalog.ingestion.name
  principal  = "account admins"
  privileges = ["ALL_PRIVILEGES"]
}

resource "databricks_grant" "bronze_account_admins" {
  catalog    = databricks_catalog.bronze.name
  principal  = "account admins"
  privileges = ["ALL_PRIVILEGES"]
}

resource "databricks_grant" "silver_account_admins" {
  catalog    = databricks_catalog.silver.name
  principal  = "account admins"
  privileges = ["ALL_PRIVILEGES"]
}

resource "databricks_grant" "gold_account_admins" {
  catalog    = databricks_catalog.gold.name
  principal  = "account admins"
  privileges = ["ALL_PRIVILEGES"]
}

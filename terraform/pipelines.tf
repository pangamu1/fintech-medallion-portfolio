resource "databricks_pipeline" "silver_scaffold" {
  name        = "silver-scaffold"
  catalog     = databricks_catalog.silver.name
  schema      = databricks_schema.silver_curated.name
  serverless  = true
  development = true
  continuous  = false
  channel     = "CURRENT"

  library {
    notebook {
      path = var.silver_scaffold_notebook_path
    }
  }
}

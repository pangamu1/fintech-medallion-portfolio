resource "databricks_volume" "ingestion_alpha_vantage_raw_jsons" {
  catalog_name = databricks_catalog.ingestion.name
  schema_name  = databricks_schema.ingestion_alpha_vantage.name
  name         = "raw_jsons"
  volume_type  = "MANAGED"
  comment      = "Landing zone for Alpha Vantage JSON files uploaded from the local lake. Read by COPY INTO into bronze.alpha_vantage.*."
}

resource "databricks_volume" "ingestion_fmp_raw_jsons" {
  catalog_name = databricks_catalog.ingestion.name
  schema_name  = databricks_schema.ingestion_fmp.name
  name         = "raw_jsons"
  volume_type  = "MANAGED"
  comment      = "Landing zone for Financial Modeling Prep JSON files uploaded from the local lake. Read by COPY INTO into bronze.fmp.*."
}
resource "databricks_volume" "ingestion_sec_raw_jsons" {
  catalog_name = databricks_catalog.ingestion.name
  schema_name  = databricks_schema.ingestion_sec.name
  name         = "raw_jsons"
  volume_type  = "MANAGED"
  comment      = "Landing zone for SEC EDGAR Form 4 JSON files. Read by the bronze_autoloader_sec_insider_transactions job into bronze.sec.insider_transactions."
}

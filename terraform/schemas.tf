resource "databricks_schema" "ingestion_alpha_vantage" {
  catalog_name = databricks_catalog.ingestion.name
  name         = "alpha_vantage"
  comment      = "Volume holding raw Alpha Vantage JSON files uploaded from the local lake."
}

resource "databricks_schema" "ingestion_fmp" {
  catalog_name = databricks_catalog.ingestion.name
  name         = "fmp"
  comment      = "Volume holding raw Financial Modeling Prep JSON files uploaded from the local lake."
}

resource "databricks_schema" "bronze_alpha_vantage" {
  catalog_name = databricks_catalog.bronze.name
  name         = "alpha_vantage"
  comment      = "Delta tables produced by COPY INTO from ingestion.alpha_vantage.raw_jsons."
}

resource "databricks_schema" "bronze_fmp" {
  catalog_name = databricks_catalog.bronze.name
  name         = "fmp"
  comment      = "Delta tables produced by COPY INTO from ingestion.fmp.raw_jsons."
}

resource "databricks_schema" "silver_fmp" {
  catalog_name = databricks_catalog.silver.name
  name         = "fmp"
  comment      = "DLT outputs from FMP Bronze: cleansed + CDC + company_scd2 (SCD2) + price/fundamental/event tables."
}

resource "databricks_schema" "silver_alpha_vantage" {
  catalog_name = databricks_catalog.silver.name
  name         = "alpha_vantage"
  comment      = "DLT output: pivoted Alpha Vantage daily prices; cross-validation feed per ADR-0019."
}

resource "databricks_schema" "gold_marts" {
  catalog_name = databricks_catalog.gold.name
  name         = "marts"
  comment      = "DBT marts: Kimball star schema (6 facts + 3 dims + 2 aggregates)."
}

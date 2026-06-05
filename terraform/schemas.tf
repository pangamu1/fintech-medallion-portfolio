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
resource "databricks_schema" "silver_dq" {
  catalog_name = databricks_catalog.silver.name
  name         = "dq"
  comment      = "DLT data-quality / observability outputs: FMP vs Alpha Vantage price cross-validation (ADR-0020); future home for file-audit + freshness checks."
}
resource "databricks_schema" "ingestion_sec" {
  catalog_name = databricks_catalog.ingestion.name
  name         = "sec"
  comment      = "Volume holding normalized SEC EDGAR Form 4 JSON files uploaded from the local lake."
}

resource "databricks_schema" "bronze_sec" {
  catalog_name = databricks_catalog.bronze.name
  name         = "sec"
  comment      = "Delta table from PySpark Autoloader on ingestion.sec.raw_jsons: insider_transactions (Form 4), rescue-mode schema evolution (ADR-0018)."
}
resource "databricks_schema" "silver_sec" {
  catalog_name = databricks_catalog.silver.name
  name         = "sec"
  comment      = "DLT output: forward-only insider-transaction event table from bronze.sec.insider_transactions (Form 4); no SCD2 per ADR-0012."
}

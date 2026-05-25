resource "databricks_catalog" "ingestion" {
  name    = "ingestion"
  comment = "Raw uploaded source files (volumes only). Boundary between Python ingestion and Databricks."
}

resource "databricks_catalog" "bronze" {
  name    = "bronze"
  comment = "Delta tables produced by COPY INTO from ingestion volumes. Append-only, schema-evolved."
}

resource "databricks_catalog" "silver" {
  name    = "silver"
  comment = "DLT outputs: cleansed + CDC + SCD2 history tables."
}

resource "databricks_catalog" "gold" {
  name    = "gold"
  comment = "DBT marts: 6 facts + 3 dims + 2 aggregates (Kimball star schema)."
}

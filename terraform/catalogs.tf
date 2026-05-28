resource "databricks_catalog" "ingestion" {
  name    = "ingestion"
  comment = "Raw uploaded source files (volumes only). Boundary between Python ingestion and Databricks."

  lifecycle {
    ignore_changes = [storage_root]
  }
}

resource "databricks_catalog" "bronze" {
  name    = "bronze"
  comment = "Delta tables produced by PySpark Autoloader from ingestion volumes. Append-only, rescue-mode schema preservation (per ADR-0018)."

  lifecycle {
    ignore_changes = [storage_root]
  }
}

resource "databricks_catalog" "silver" {
  name    = "silver"
  comment = "DLT outputs: cleansed + CDC + SCD2 history tables."

  lifecycle {
    ignore_changes = [storage_root]
  }
}

resource "databricks_catalog" "gold" {
  name    = "gold"
  comment = "DBT marts: 6 facts + 3 dims + 2 aggregates (Kimball star schema)."

  lifecycle {
    ignore_changes = [storage_root]
  }
}

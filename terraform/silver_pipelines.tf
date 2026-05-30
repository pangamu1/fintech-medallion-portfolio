# Silver DLT pipelines — Spark Declarative Pipelines on serverless compute.
# Syncs a .py transformation file from databricks/dlt/silver/ into the workspace
# and runs it as a triggered DLT pipeline writing into the `silver` UC catalog.
# See ADR-0002 (Silver = Databricks DLT) and feat/silver-dlt plan CP1 decisions.

resource "databricks_workspace_file" "silver_profile_py" {
  source = "${path.module}/../databricks/dlt/silver/silver_profile.py"
  path   = "/Users/piruthviraj5@outlook.com/silver/silver_profile.py"
}

resource "databricks_pipeline" "silver_events" {
  name       = "silver_events"
  serverless = true
  catalog    = "silver"
  schema     = "fmp"
  channel    = "CURRENT"
  continuous = false

  library {
    file {
      path = databricks_workspace_file.silver_profile_py.workspace_path
    }
  }
}
resource "databricks_workspace_file" "silver_prices_py" {
  source = "${path.module}/../databricks/dlt/silver/silver_prices.py"
  path   = "/Users/piruthviraj5@outlook.com/silver/silver_prices.py"
}

resource "databricks_workspace_file" "silver_fundamentals_py" {
  source = "${path.module}/../databricks/dlt/silver/silver_fundamentals.py"
  path   = "/Users/piruthviraj5@outlook.com/silver/silver_fundamentals.py"
}

resource "databricks_pipeline" "silver_prices" {
  name       = "silver_prices"
  serverless = true
  catalog    = "silver"
  schema     = "fmp"
  channel    = "CURRENT"
  continuous = false

  library {
    file {
      path = databricks_workspace_file.silver_prices_py.workspace_path
    }
  }
}

resource "databricks_pipeline" "silver_fundamentals" {
  name       = "silver_fundamentals"
  serverless = true
  catalog    = "silver"
  schema     = "fmp"
  channel    = "CURRENT"
  continuous = false

  library {
    file {
      path = databricks_workspace_file.silver_fundamentals_py.workspace_path
    }
  }
}
resource "databricks_workspace_file" "silver_alpha_vantage_py" {
  source = "${path.module}/../databricks/dlt/silver/silver_alpha_vantage.py"
  path   = "/Users/piruthviraj5@outlook.com/silver/silver_alpha_vantage.py"
}

resource "databricks_pipeline" "silver_alpha_vantage" {
  name       = "silver_alpha_vantage"
  serverless = true
  catalog    = "silver"
  schema     = "alpha_vantage"
  channel    = "CURRENT"
  continuous = false

  library {
    file {
      path = databricks_workspace_file.silver_alpha_vantage_py.workspace_path
    }
  }
}

# Bronze Autoloader jobs — one per (source, endpoint) pair = 11 jobs total.
# Each job runs databricks/jobs/bronze_autoloader/run.py on serverless general-
# purpose compute. PySpark Autoloader streams JSONs from the ingestion volumes
# into bronze.<source>.<endpoint> Delta tables. See ADR-0018.

locals {
  bronze_jobs = {
    "fmp.balance_sheet"             = { source = "fmp", endpoint = "balance_sheet" }
    "fmp.cash_flow"                 = { source = "fmp", endpoint = "cash_flow" }
    "fmp.dividends"                 = { source = "fmp", endpoint = "dividends" }
    "fmp.earnings"                  = { source = "fmp", endpoint = "earnings" }
    "fmp.historical_price_adjusted" = { source = "fmp", endpoint = "historical_price_adjusted" }
    "fmp.historical_price_full"     = { source = "fmp", endpoint = "historical_price_full" }
    "fmp.income_statement"          = { source = "fmp", endpoint = "income_statement" }
    "fmp.key_metrics"               = { source = "fmp", endpoint = "key_metrics" }
    "fmp.profile"                   = { source = "fmp", endpoint = "profile" }
    "fmp.splits"                    = { source = "fmp", endpoint = "splits" }
  }
}
resource "databricks_workspace_file" "bronze_autoloader_run_py" {
  source = "${path.module}/../databricks/jobs/bronze_autoloader/run.py"
  path   = "/Users/piruthviraj5@outlook.com/bronze_autoloader/run.py"
}
resource "databricks_job" "bronze_autoloader" {
  for_each = local.bronze_jobs

  name = "bronze_autoloader_${each.value.source}_${each.value.endpoint}"

  environment {
    environment_key = "default"
    spec {
      environment_version = "5"
    }
  }

  task {
    task_key        = "run"
    environment_key = "default"

    spark_python_task {
      python_file = databricks_workspace_file.bronze_autoloader_run_py.workspace_path
      parameters  = ["--source", each.value.source, "--endpoint", each.value.endpoint]
      source      = "WORKSPACE"
    }
  }
}

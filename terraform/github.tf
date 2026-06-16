resource "github_branch_protection" "main" {
  repository_id       = var.github_repo
  pattern             = "main"
  enforce_admins      = true
  allows_deletions    = false
  allows_force_pushes = false

  required_pull_request_reviews {
    dismiss_stale_reviews           = true
    required_approving_review_count = 0
  }
}

resource "github_actions_secret" "databricks_host" {
  repository  = var.github_repo
  secret_name = "DATABRICKS_HOST"
  value       = var.databricks_host
}

resource "github_actions_secret" "databricks_token" {
  repository  = var.github_repo
  secret_name = "DATABRICKS_TOKEN"
  value       = var.databricks_token
}
resource "github_actions_secret" "dbt_cloud_config" {
  repository  = var.github_repo
  secret_name = "DBT_CLOUD_CONFIG"
  value       = var.dbt_cloud_config
}

resource "github_actions_secret" "dbt_cloud_api_token" {
  repository  = var.github_repo
  secret_name = "DBT_CLOUD_API_TOKEN"
  value       = var.dbt_cloud_api_token
}
resource "github_actions_secret" "google_service_account" {
  repository  = var.github_repo
  secret_name = "GOOGLE_SERVICE_ACCOUNT"
  value       = var.google_service_account
}
resource "github_actions_secret" "databricks_http_path" {
  repository  = var.github_repo
  secret_name = "DATABRICKS_HTTP_PATH"
  value       = var.databricks_http_path
}
resource "github_actions_secret" "fmp_api_key" {
  repository  = var.github_repo
  secret_name = "FMP_API_KEY"
  value       = var.fmp_api_key
}

resource "github_actions_secret" "alpha_vantage_api_key" {
  repository  = var.github_repo
  secret_name = "ALPHA_VANTAGE_API_KEY"
  value       = var.alpha_vantage_api_key
}
resource "github_actions_variable" "bronze_job_ids" {
  repository    = var.github_repo
  variable_name = "BRONZE_JOB_IDS"
  value = jsonencode([
    for key, job in databricks_job.bronze_autoloader : { name = key, id = job.id }
  ])
}

resource "github_actions_variable" "silver_source_pipeline_ids" {
  repository    = var.github_repo
  variable_name = "SILVER_SOURCE_PIPELINE_IDS"
  value = jsonencode([
    { name = "silver_events", id = databricks_pipeline.silver_events.id },
    { name = "silver_prices", id = databricks_pipeline.silver_prices.id },
    { name = "silver_fundamentals", id = databricks_pipeline.silver_fundamentals.id },
    { name = "silver_alpha_vantage", id = databricks_pipeline.silver_alpha_vantage.id },
    { name = "silver_sec", id = databricks_pipeline.silver_sec.id },
  ])
}

resource "github_actions_variable" "silver_dq_pipeline_id" {
  repository    = var.github_repo
  variable_name = "SILVER_DQ_PIPELINE_ID"
  value         = databricks_pipeline.silver_dq.id
}

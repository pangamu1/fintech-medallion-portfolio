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

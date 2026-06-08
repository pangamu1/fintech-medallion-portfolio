variable "databricks_host" {
  description = "Databricks workspace URL."
  type        = string
}

variable "databricks_token" {
  description = "Databricks personal access token used by the databricks provider."
  type        = string
  sensitive   = true
}

variable "github_owner" {
  description = "GitHub user or org that owns the repository."
  type        = string
}

variable "github_token" {
  description = "GitHub PAT with repo + admin:repo_hook scopes for the integrations/github provider."
  type        = string
  sensitive   = true
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
}
variable "dbt_cloud_config" {
  description = "Full contents of ~/.dbt/dbt_cloud.yml — dbt Cloud CLI auth used by the PR Slim-CI workflow (DBT_CLOUD_CONFIG Actions secret)."
  type        = string
  sensitive   = true
}

variable "dbt_cloud_api_token" {
  description = "dbt Cloud service token (Account Admin) used by the CD workflow to trigger the prod Deploy job via the Admin API (DBT_CLOUD_API_TOKEN Actions secret)."
  type        = string
  sensitive   = true
}
variable "google_service_account" {
  description = "Full JSON contents of the GCP service-account key (bi-sheets-writer) used by the BI reverse-ETL workflow to write gold marts into the serving Google Sheet (GOOGLE_SERVICE_ACCOUNT Actions secret)."
  type        = string
  sensitive   = true
}
variable "databricks_http_path" {
  description = "Databricks SQL warehouse HTTP path used by the BI reverse-ETL workflow (DATABRICKS_HTTP_PATH Actions secret)."
  type        = string
}

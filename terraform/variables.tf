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

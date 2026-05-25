provider "databricks" {
  host  = var.databricks_host
  token = var.databricks_token
}

provider "github" {
  owner = var.github_owner
  token = var.github_token
}
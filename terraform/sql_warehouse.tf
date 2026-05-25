resource "databricks_sql_endpoint" "bootstrap" {
  name                      = "Serverless Starter Warehouse"
  cluster_size              = "2X-Small"
  min_num_clusters          = 1
  max_num_clusters          = 1
  auto_stop_mins            = 10
  enable_serverless_compute = true
  warehouse_type            = "PRO"

  channel {
    name = "CHANNEL_NAME_CURRENT"
  }
}

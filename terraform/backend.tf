terraform {
  cloud {
    organization = "pangamu1-fintech"

    workspaces {
      name = "fintech-medallion-portfolio-bootstrap"
    }
  }
}
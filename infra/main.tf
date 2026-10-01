# Scrappy's infrastructure. The state bucket this points at is created once by
# infra/bootstrap/, which is a separate configuration with its own local state.
#
#   cd infra && terraform init && terraform plan

terraform {
  required_version = ">= 1.11"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    bucket = "scrappy-tfstate-224772449441"
    key    = "scrappy/terraform.tfstate"
    region = "us-east-1"

    # Native S3 locking (Terraform 1.11+): no DynamoDB table, so no monthly cost.
    use_lockfile = true
    encrypt      = true
  }
}

provider "aws" {
  region = var.region

  # Every resource is tagged, so the bill can always be traced back to this project.
  default_tags {
    tags = {
      project = "scrappy"
    }
  }
}

variable "region" {
  description = "AWS region for every Scrappy resource."
  type        = string
  default     = "us-east-1"
}

data "aws_caller_identity" "current" {}

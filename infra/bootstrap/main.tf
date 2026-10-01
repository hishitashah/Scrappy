# Terraform's own state has to live somewhere before the main configuration can use a
# remote backend — this is that chicken-and-egg step. It keeps state locally, is applied
# once by hand, and then is left alone.
#
#   cd infra/bootstrap && terraform init && terraform apply

terraform {
  required_version = ">= 1.11"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.region

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

# Bucket names are globally unique across all of AWS, so the account id keeps ours distinct.
data "aws_caller_identity" "current" {}

locals {
  state_bucket = "scrappy-tfstate-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket" "state" {
  bucket = local.state_bucket

  # State is the record of everything that exists; losing it means losing track of the
  # infrastructure. Terraform can recreate resources, not knowledge of them.
  lifecycle {
    prevent_destroy = true
  }
}

# Every apply writes a new version, so a bad state file can be rolled back.
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# State can contain sensitive values, so the bucket is private in every way available.
resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

output "state_bucket" {
  description = "Put this in the backend block of infra/main.tf."
  value       = aws_s3_bucket.state.id
}

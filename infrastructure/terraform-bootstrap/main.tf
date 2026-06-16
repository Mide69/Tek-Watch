# Bootstrap Terraform — applied ONCE, by hand, with privileged human (SSO)
# credentials. This creates the trust relationship that lets GitHub Actions
# assume an IAM role via OIDC — chicken-and-egg by nature, since CI can't use
# OIDC to create the very thing that lets it use OIDC. Separate from
# infrastructure/terraform/ (the app's per-environment infra) deliberately:
# this changes rarely, has its own lifecycle, and a mistake here shouldn't be
# entangled with routine app infra applies.
#
# Run this with the same profile you used for the state-backend bootstrap:
#   cd infrastructure/terraform-bootstrap
#   export AWS_PROFILE=tekwatch
#   terraform init
#   terraform apply

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }

  backend "s3" {
    bucket         = "tek-watch-terraform-state"
    key            = "tek-watch/bootstrap/terraform.tfstate"
    region         = "eu-west-2"
    encrypt        = true
    dynamodb_table = "tek-watch-terraform-locks"
  }
}

provider "aws" {
  region = "eu-west-2"

  default_tags {
    tags = {
      Project   = "tek-watch"
      ManagedBy = "terraform-bootstrap"
    }
  }
}

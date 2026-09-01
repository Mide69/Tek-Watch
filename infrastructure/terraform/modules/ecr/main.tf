terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      configuration_aliases = [aws.us_east_1]
    }
  }
}

variable "name_prefix" { type = string }
variable "environment" { type = string }

variable "project" {
  description = "Repository name prefix, without the environment. ECR repos are shared across environments on purpose — see the comment on aws_ecr_repository.repos."
  type        = string
  default     = "tek-watch"
}

locals {
  repos = ["agent", "api", "ingest-consumer"]
}

# Deliberately NOT per-environment. These were "${name_prefix}-${service}",
# giving tek-watch-prod-api, while every workflow pushes to tek-watch-api — so
# CI could never actually deploy, because the repositories it targeted did not
# exist.
#
# Shared repos are the right side of that mismatch. The CI is written for
# build-once-promote: build-and-push runs BEFORE any deploy job and so cannot
# know which environment it is building for. Per-environment repos would force
# a rebuild per environment, meaning the image shipped to prod is not the image
# that was tested. One repo per service, promoted by tag, keeps that guarantee
# and stores one copy of each image instead of one per environment.
resource "aws_ecr_repository" "repos" {
  for_each             = toset(local.repos)
  name                 = "${var.project}-${each.key}"
  image_tag_mutability = "MUTABLE"

  # Non-prod repos delete with their images on `terraform destroy` — without
  # this, a teardown fails on "repository not empty" and leaves the repos (and
  # their image storage) behind. Prod requires emptying by hand first.
  force_delete = var.environment != "prod"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Name = "${var.project}-${each.key}" }
}

resource "aws_ecr_lifecycle_policy" "repos" {
  for_each   = aws_ecr_repository.repos
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}

output "agent_repository_url" { value = aws_ecr_repository.repos["agent"].repository_url }
output "api_repository_url" { value = aws_ecr_repository.repos["api"].repository_url }
output "consumer_repository_url" { value = aws_ecr_repository.repos["ingest-consumer"].repository_url }

# ── Public registry for the customer agent ────────────────────────────────────
#
# Customers run this agent inside their own AWS account, so their account has to
# be able to pull the image. The private repository above cannot serve that: it
# is readable only from this account, so a customer's CloudFormation stack failed
# on AccessDenied at image pull, and the template shipped pointing at a
# documentation placeholder account anyway. Onboarding could not complete.
#
# A per-customer repository policy was the alternative and was rejected. An ECR
# repository policy is capped around 10 KB, roughly a couple of hundred customer
# accounts, after which onboarding would stop working with no warning. It also
# puts an IAM write on the signup path.
#
# The image is collector code. It carries no credentials and no customer data —
# the Customer ID, API key and queue URL all arrive as environment variables at
# runtime — so publishing it exposes how the agent works and nothing about who
# uses it. This is what every comparable vendor agent does.
#
# ECR Public lives only in us-east-1, whatever region the rest of this is in.
resource "aws_ecrpublic_repository" "agent" {
  provider        = aws.us_east_1
  repository_name = "${var.project}-agent"

  catalog_data {
    about_text        = "Read-only AWS monitoring agent for Tek Watch. Runs in your own account and publishes metrics to your Tek Watch dashboard."
    architectures     = ["x86-64"]
    operating_systems = ["Linux"]
    usage_text        = "Deployed by the CloudFormation template available from your Tek Watch dashboard. Not intended to be run by hand."
  }

  tags = { Name = "${var.project}-agent-public" }
}

output "agent_public_repository_uri" {
  value = aws_ecrpublic_repository.agent.repository_uri
}

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

variable "name_prefix" { type = string }

locals {
  repos = ["agent", "api", "ingest-consumer"]
}

resource "aws_ecr_repository" "repos" {
  for_each             = toset(local.repos)
  name                 = "${var.name_prefix}-${each.key}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Name = "${var.name_prefix}-${each.key}" }
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

output "agent_repository_url"    { value = aws_ecr_repository.repos["agent"].repository_url }
output "api_repository_url"      { value = aws_ecr_repository.repos["api"].repository_url }
output "consumer_repository_url" { value = aws_ecr_repository.repos["ingest-consumer"].repository_url }

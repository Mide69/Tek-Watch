variable "name_prefix" { type = string }
variable "environment" { type = string }

variable "secret_values" {
  type      = map(string)
  sensitive = true
}

resource "aws_secretsmanager_secret" "main" {
  name                    = "${var.name_prefix}/config"
  description             = "Tek Watch platform configuration secrets"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = { Name = "${var.name_prefix}-config" }
}

resource "aws_secretsmanager_secret_version" "main" {
  secret_id     = aws_secretsmanager_secret.main.id
  secret_string = jsonencode(var.secret_values)

  lifecycle {
    ignore_changes = [secret_string]
  }
}

output "secret_arn" { value = aws_secretsmanager_secret.main.arn }
output "secret_name" { value = aws_secretsmanager_secret.main.name }

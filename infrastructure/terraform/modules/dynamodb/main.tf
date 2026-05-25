variable "name_prefix" { type = string }
variable "environment" { type = string }

# ── Customers table ───────────────────────────────────────────────────────────

resource "aws_dynamodb_table" "customers" {
  name         = "${var.name_prefix}-customers"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "customer_id"
  range_key    = "SK"

  attribute {
    name = "customer_id"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }

  point_in_time_recovery {
    enabled = var.environment == "prod"
  }

  tags = { Name = "${var.name_prefix}-customers" }
}

# ── Alerts table ──────────────────────────────────────────────────────────────

resource "aws_dynamodb_table" "alerts" {
  name         = "${var.name_prefix}-alerts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "customer_id"
  range_key    = "SK"

  attribute {
    name = "customer_id"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }

  # TTL — auto-expire resolved alerts after 90 days
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = var.environment == "prod"
  }

  tags = { Name = "${var.name_prefix}-alerts" }
}

# ── Thresholds table ──────────────────────────────────────────────────────────

resource "aws_dynamodb_table" "thresholds" {
  name         = "${var.name_prefix}-thresholds"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }

  tags = { Name = "${var.name_prefix}-thresholds" }
}

output "customers_table_name" { value = aws_dynamodb_table.customers.name }
output "alerts_table_name"    { value = aws_dynamodb_table.alerts.name }
output "thresholds_table_name"{ value = aws_dynamodb_table.thresholds.name }
output "customers_table_arn"  { value = aws_dynamodb_table.customers.arn }
output "alerts_table_arn"     { value = aws_dynamodb_table.alerts.arn }
output "thresholds_table_arn" { value = aws_dynamodb_table.thresholds.arn }

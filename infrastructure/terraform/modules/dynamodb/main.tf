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

# ── Heartbeats table (agent silence detector) ─────────────────────────────────
# Hash key matches the customer_id written by the agent and read by the
# silence-detector Lambda.  No sort key — one row per customer.

resource "aws_dynamodb_table" "heartbeats" {
  name         = "${var.name_prefix}-heartbeats"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "customer_id"

  attribute {
    name = "customer_id"
    type = "S"
  }

  # TTL — stale heartbeats auto-expire after 7 days (keeps the table lean)
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = { Name = "${var.name_prefix}-heartbeats" }
}

# ── Usage metering table ──────────────────────────────────────────────────────
# PK=customer_id, SK=month (YYYY-MM) — atomic ADD counters per endpoint

resource "aws_dynamodb_table" "usage" {
  name         = "${var.name_prefix}-usage"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "customer_id"
  range_key    = "month"

  attribute {
    name = "customer_id"
    type = "S"
  }
  attribute {
    name = "month"
    type = "S"
  }

  # TTL — auto-expire records older than 13 months (keep rolling year + 1)
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = { Name = "${var.name_prefix}-usage" }
}

# ── Admin audit log table ─────────────────────────────────────────────────────
# PK=admin_id, SK={timestamp}#{event_id} — append-only, chronological queries

resource "aws_dynamodb_table" "audit_log" {
  name         = "${var.name_prefix}-audit-log"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "admin_id"
  range_key    = "sk"

  attribute {
    name = "admin_id"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }

  # PITR on in all environments — audit logs are compliance data
  point_in_time_recovery {
    enabled = true
  }

  tags = { Name = "${var.name_prefix}-audit-log" }
}

output "customers_table_name" { value = aws_dynamodb_table.customers.name }
output "alerts_table_name" { value = aws_dynamodb_table.alerts.name }
output "thresholds_table_name" { value = aws_dynamodb_table.thresholds.name }
output "heartbeats_table_name" { value = aws_dynamodb_table.heartbeats.name }
output "usage_table_name" { value = aws_dynamodb_table.usage.name }
output "audit_log_table_name" { value = aws_dynamodb_table.audit_log.name }
output "customers_table_arn" { value = aws_dynamodb_table.customers.arn }
output "alerts_table_arn" { value = aws_dynamodb_table.alerts.arn }
output "thresholds_table_arn" { value = aws_dynamodb_table.thresholds.arn }
output "heartbeats_table_arn" { value = aws_dynamodb_table.heartbeats.arn }
output "usage_table_arn" { value = aws_dynamodb_table.usage.arn }
output "audit_log_table_arn" { value = aws_dynamodb_table.audit_log.arn }

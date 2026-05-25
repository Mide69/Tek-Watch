variable "name_prefix"             { type = string }
variable "memory_retention_hours"  { type = number }
variable "magnetic_retention_days" { type = number }

resource "aws_timestreamwrite_database" "main" {
  database_name = var.name_prefix
  tags          = { Name = var.name_prefix }
}

resource "aws_timestreamwrite_table" "metrics" {
  database_name = aws_timestreamwrite_database.main.database_name
  table_name    = "metrics"

  retention_properties {
    memory_store_retention_period_in_hours  = var.memory_retention_hours
    magnetic_store_retention_period_in_days = var.magnetic_retention_days
  }

  magnetic_store_write_properties {
    enable_magnetic_store_writes = true
  }

  tags = { Name = "${var.name_prefix}-metrics" }
}

resource "aws_timestreamwrite_table" "events" {
  database_name = aws_timestreamwrite_database.main.database_name
  table_name    = "events"

  retention_properties {
    memory_store_retention_period_in_hours  = var.memory_retention_hours
    magnetic_store_retention_period_in_days = var.magnetic_retention_days
  }

  magnetic_store_write_properties {
    enable_magnetic_store_writes = true
  }

  tags = { Name = "${var.name_prefix}-events" }
}

output "database_name"      { value = aws_timestreamwrite_database.main.database_name }
output "metrics_table_name" { value = aws_timestreamwrite_table.metrics.table_name }
output "events_table_name"  { value = aws_timestreamwrite_table.events.table_name }
output "database_arn"       { value = aws_timestreamwrite_database.main.arn }
output "table_arns" {
  value = [
    aws_timestreamwrite_table.metrics.arn,
    aws_timestreamwrite_table.events.arn,
  ]
}

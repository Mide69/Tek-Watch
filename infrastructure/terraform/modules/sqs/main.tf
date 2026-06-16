variable "name_prefix" { type = string }
variable "visibility_timeout_seconds" { type = number }
variable "message_retention_seconds" { type = number }
variable "dlq_max_receive_count" { type = number }

# ── Dead Letter Queue ─────────────────────────────────────────────────────────

resource "aws_sqs_queue" "dlq" {
  name                       = "${var.name_prefix}-ingest-dlq"
  message_retention_seconds  = 1209600 # 14 days for DLQ
  visibility_timeout_seconds = var.visibility_timeout_seconds

  tags = { Name = "${var.name_prefix}-ingest-dlq" }
}

# ── Ingest Queue ──────────────────────────────────────────────────────────────

resource "aws_sqs_queue" "ingest" {
  name                       = "${var.name_prefix}-ingest"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.dlq_max_receive_count
  })

  tags = { Name = "${var.name_prefix}-ingest" }
}

# ── Queue Policy — allow any AWS account to send (customers use IAM roles) ────

resource "aws_sqs_queue_policy" "ingest" {
  queue_url = aws_sqs_queue.ingest.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowSendFromAnyAccount"
      Effect    = "Allow"
      Principal = { AWS = "*" }
      Action    = ["sqs:SendMessage", "sqs:SendMessageBatch"]
      Resource  = aws_sqs_queue.ingest.arn
      Condition = {
        StringEquals = {
          "aws:PrincipalOrgID" = "*"
        }
      }
    }]
  })
}

output "ingest_queue_url" { value = aws_sqs_queue.ingest.url }
output "ingest_queue_arn" { value = aws_sqs_queue.ingest.arn }
output "ingest_queue_name" { value = aws_sqs_queue.ingest.name }
output "dlq_arn" { value = aws_sqs_queue.dlq.arn }
output "dlq_name" { value = aws_sqs_queue.dlq.name }

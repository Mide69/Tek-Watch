variable "publisher_org_id" {
  description = "AWS Organizations id whose accounts may publish to the ingest queue."
  type        = string
}

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
      Sid       = "AllowSendFromCustomerAgents"
      Effect    = "Allow"
      Principal = { AWS = "*" }
      # SQS resource (queue) policies validate against an older action list
      # than IAM identity policies — "sqs:SendMessageBatch" isn't recognized
      # here ("Please refer to the appropriate WSDL...") even though it's a
      # valid IAM action. SendMessageBatch calls are authorized by the same
      # underlying SendMessage permission, so this alone is sufficient.
      Action   = ["sqs:SendMessage"]
      Resource = aws_sqs_queue.ingest.arn
      # This was StringEquals on "*", which is not a wildcard: StringEquals
      # compares literally, so it matched only a principal whose organization
      # id is the single character "*". Nothing has that. The statement granted
      # nothing at all, and every customer agent would have failed on
      # AccessDenied at its first publish — after the customer had already run
      # a CloudFormation stack in their own account, which is the worst place
      # to discover it.
      #
      # Scoped to this organization for now. That covers agents in accounts we
      # own, which is what exists today. It does NOT cover an external
      # customer, whose account is in their own organization: see
      # var.additional_publisher_account_ids below, and the note in the module
      # header about moving ingest behind the API.
      Condition = {
        StringEquals = {
          "aws:PrincipalOrgID" = var.publisher_org_id
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

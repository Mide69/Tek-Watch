variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod"
  }
}

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-west-2"
}

variable "project" {
  description = "Project name prefix for all resources"
  type        = string
  default     = "tek-watch"
}

# ── Networking ────────────────────────────────────────────────────────────────

variable "vpc_cidr" {
  description = "CIDR block for the central account VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones to deploy into"
  type        = list(string)
  default     = ["eu-west-2a", "eu-west-2b", "eu-west-2c"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (one per AZ)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (one per AZ)"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}

variable "enable_nat_gateway" {
  description = "Create NAT gateways for private-subnet egress. False runs ECS tasks in public subnets instead (SG-locked to ALB-only inbound) to skip the ~$33-45/mo per-gateway cost."
  type        = bool
  default     = true
}

# ── ECS ───────────────────────────────────────────────────────────────────────

variable "api_cpu" {
  description = "CPU units for the API ECS task (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "api_memory" {
  description = "Memory (MB) for the API ECS task"
  type        = number
  default     = 1024
}

variable "api_desired_count" {
  description = "Desired number of API task replicas"
  type        = number
  default     = 2
}

variable "consumer_cpu" {
  description = "CPU units for the ingest consumer ECS task"
  type        = number
  default     = 256
}

variable "consumer_memory" {
  description = "Memory (MB) for the ingest consumer ECS task"
  type        = number
  default     = 512
}

variable "consumer_desired_count" {
  description = "Desired number of ingest consumer task replicas"
  type        = number
  default     = 2
}

variable "agent_cpu" {
  description = "CPU units for the self-hosted agent ECS task (matches the customer CFN template default)"
  type        = number
  default     = 512
}

variable "agent_memory" {
  description = "Memory (MB) for the self-hosted agent ECS task"
  type        = number
  default     = 1024
}

variable "agent_schedule_expression" {
  description = "EventBridge schedule for the self-hosted agent's scheduled ECS task"
  type        = string
  default     = "rate(5 minutes)"
}

variable "enable_self_hosted_agent" {
  description = "Run the central account's own monitoring agent on a schedule. Costs a Fargate task launch per firing, so keep it off until TEK_WATCH_API_KEY is configured."
  type        = bool
  default     = true
}

variable "enable_container_insights" {
  description = "ECS Container Insights (per-task custom metrics, billed per metric). Logs and alarms are unaffected when disabled."
  type        = bool
  default     = true
}

variable "api_use_spot" {
  description = "Run the API service on FARGATE_SPOT (~70% cheaper, occasional 2-minute-notice reclaims)."
  type        = bool
  default     = false
}

variable "ops_alert_email" {
  description = "Address subscribed to the ops-alerts SNS topic. Empty means alarms fire into a topic with no subscribers and nobody is told. Set it in a gitignored *.auto.tfvars file, not environments/*.tfvars — this repo is public."
  type        = string
  default     = ""
}

variable "ingest_queue_depth_threshold" {
  description = "Messages visible before the ingest-queue alarm fires. Set to 0 whenever consumer_desired_count is 0."
  type        = number
  default     = 10000
}

variable "ingest_queue_depth_evaluation_periods" {
  description = "5-minute periods the ingest-queue threshold must be breached before alarming."
  type        = number
  default     = 3
}

# ── SQS ───────────────────────────────────────────────────────────────────────

variable "sqs_visibility_timeout_seconds" {
  description = "SQS message visibility timeout"
  type        = number
  default     = 300
}

variable "sqs_message_retention_seconds" {
  description = "SQS message retention period"
  type        = number
  default     = 345600 # 4 days
}

variable "sqs_dlq_max_receive_count" {
  description = "Number of receive attempts before moving to DLQ"
  type        = number
  default     = 3
}

# ── Cognito ───────────────────────────────────────────────────────────────────

variable "admin_google_client_id" {
  description = "Google OAuth client ID for admin SSO (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "admin_google_client_secret" {
  description = "Google OAuth client secret for admin SSO (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

# ── Secrets ───────────────────────────────────────────────────────────────────

variable "anthropic_api_key" {
  description = "Anthropic API key for Claude anomaly detection"
  type        = string
  sensitive   = true
  default     = ""
}

# ── DNS ───────────────────────────────────────────────────────────────────────

variable "domain_name" {
  description = "Base domain name (e.g. tekwatch.io)"
  type        = string
  default     = "tekwatch.io"
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for the ALB HTTPS listener (must be in eu-west-2)"
  type        = string
  default     = ""
}

variable "cloudfront_certificate_arn" {
  description = "Externally-managed ACM certificate ARN for CloudFront (must be in us-east-1). Ignored when enable_custom_domain and attach_custom_domain are both true, since terraform then manages its own."
  type        = string
  default     = ""
}

variable "enable_custom_domain" {
  description = "Request a us-east-1 ACM certificate covering the dashboard and admin domains. Phase 1: creates the request and prints the DNS validation records to add at your DNS host."
  type        = bool
  default     = false
}

variable "attach_custom_domain" {
  description = "Attach the certificate above to both CloudFront distributions. Phase 2 — only set true once the certificate reports ISSUED, because CloudFront rejects one that is still PENDING_VALIDATION."
  type        = bool
  default     = false
}

variable "self_hosted_agent_api_key" {
  description = "API key issued to the central account's own monitoring agent. Set in a gitignored *.auto.tfvars — this repo is public."
  type        = string
  default     = ""
  sensitive   = true
}

variable "self_hosted_agent_customer_id" {
  description = "Customer ID the self-hosted agent reports as. Must match a record created via the admin portal (TT-XXXX)."
  type        = string
  default     = "TEK-WATCH-INTERNAL"
}

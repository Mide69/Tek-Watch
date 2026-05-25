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
  default     = "tribe-watch"
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

# ── Timestream ────────────────────────────────────────────────────────────────

variable "timestream_memory_retention_hours" {
  description = "Hours to retain data in Timestream memory store"
  type        = number
  default     = 168  # 7 days
}

variable "timestream_magnetic_retention_days" {
  description = "Days to retain data in Timestream magnetic store"
  type        = number
  default     = 90
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
  default     = 345600  # 4 days
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
  description = "Base domain name (e.g. tribewatch.io)"
  type        = string
  default     = "tribewatch.io"
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for the ALB HTTPS listener (must be in eu-west-2)"
  type        = string
  default     = ""
}

variable "cloudfront_certificate_arn" {
  description = "ACM certificate ARN for CloudFront (must be in us-east-1)"
  type        = string
  default     = ""
}

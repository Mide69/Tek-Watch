# ── Dev environment configuration ────────────────────────────────────────────
environment = "dev"
aws_region  = "eu-west-2"

# Networking — single AZ in dev to save cost
availability_zones   = ["eu-west-2a", "eu-west-2b"]
private_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24"]
public_subnet_cidrs  = ["10.0.101.0/24", "10.0.102.0/24"]

# ECS — minimal sizing for dev
api_cpu            = 256
api_memory         = 512
api_desired_count  = 1

consumer_cpu           = 256
consumer_memory        = 512
consumer_desired_count = 1

# Timestream — shorter retention in dev
timestream_memory_retention_hours  = 24
timestream_magnetic_retention_days = 7

# SQS
sqs_visibility_timeout_seconds = 300
sqs_message_retention_seconds  = 86400   # 1 day in dev
sqs_dlq_max_receive_count      = 3

# Domain — no cert needed for dev (HTTP only via ALB DNS)
domain_name         = "dev.tribewatch.io"
acm_certificate_arn = ""

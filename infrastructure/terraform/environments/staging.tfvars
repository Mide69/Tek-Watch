# ── Staging environment configuration ────────────────────────────────────────
environment = "staging"
aws_region  = "eu-west-2"

availability_zones   = ["eu-west-2a", "eu-west-2b", "eu-west-2c"]
private_subnet_cidrs = ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24"]
public_subnet_cidrs  = ["10.1.101.0/24", "10.1.102.0/24", "10.1.103.0/24"]

# ECS — production-like sizing
api_cpu            = 512
api_memory         = 1024
api_desired_count  = 2

consumer_cpu           = 256
consumer_memory        = 512
consumer_desired_count = 2

# Timestream — 7-day memory, 30-day magnetic
timestream_memory_retention_hours  = 168
timestream_magnetic_retention_days = 30

# SQS
sqs_visibility_timeout_seconds = 300
sqs_message_retention_seconds  = 345600  # 4 days
sqs_dlq_max_receive_count      = 3

domain_name         = "staging.tribewatch.io"
acm_certificate_arn = ""   # Set via GitHub secret ACM_CERT_ARN_STAGING

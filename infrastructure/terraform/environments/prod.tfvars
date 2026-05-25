# ── Production environment configuration ─────────────────────────────────────
environment = "prod"
aws_region  = "eu-west-2"

availability_zones   = ["eu-west-2a", "eu-west-2b", "eu-west-2c"]
private_subnet_cidrs = ["10.2.1.0/24", "10.2.2.0/24", "10.2.3.0/24"]
public_subnet_cidrs  = ["10.2.101.0/24", "10.2.102.0/24", "10.2.103.0/24"]

# ECS — full HA sizing
api_cpu            = 1024
api_memory         = 2048
api_desired_count  = 3

consumer_cpu           = 512
consumer_memory        = 1024
consumer_desired_count = 3

# Timestream — full retention
timestream_memory_retention_hours  = 168   # 7 days
timestream_magnetic_retention_days = 90

# SQS
sqs_visibility_timeout_seconds = 300
sqs_message_retention_seconds  = 345600   # 4 days
sqs_dlq_max_receive_count      = 3

domain_name         = "tribewatch.io"
acm_certificate_arn = ""   # Set via GitHub secret ACM_CERT_ARN_PROD

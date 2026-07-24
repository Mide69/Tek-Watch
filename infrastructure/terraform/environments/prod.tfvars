# ── Production environment configuration ─────────────────────────────────────
# Cost-minimum sizing for pre-revenue launch (~$55-90/mo). Bump
# api_desired_count/consumer_desired_count back to 2-3, restore 3 AZs, and
# set enable_nat_gateway = true once real paying-customer traffic justifies
# the HA spend — every value below is a one-line tfvars change + apply.
environment = "prod"
aws_region  = "eu-west-2"

availability_zones   = ["eu-west-2a", "eu-west-2b"] # 2 is the ALB minimum
private_subnet_cidrs = ["10.2.1.0/24", "10.2.2.0/24"]
public_subnet_cidrs  = ["10.2.101.0/24", "10.2.102.0/24"]

# No NAT gateway — tasks run in public subnets, still locked down to
# ALB-only inbound via security groups. Saves ~$65-90/mo vs 2-3 NAT gateways.
enable_nat_gateway = false

# ECS — minimum viable sizing (matches proven dev sizing)
api_cpu           = 256
api_memory        = 512
api_desired_count = 1

consumer_cpu           = 256
consumer_memory        = 512
consumer_desired_count = 1

# SQS
sqs_visibility_timeout_seconds = 300
sqs_message_retention_seconds  = 345600 # 4 days
sqs_dlq_max_receive_count      = 3

domain_name         = "tekwatch.io"
acm_certificate_arn = "" # Set via GitHub secret ACM_CERT_ARN_PROD

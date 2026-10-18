# ── Dev environment configuration ────────────────────────────────────────────
environment = "dev"
aws_region  = "eu-west-2"

# vpc_cidr is intentionally omitted: dev is the one environment whose subnets
# match var.vpc_cidr's 10.0.0.0/16 default. prod and staging must set it.
availability_zones   = ["eu-west-2a", "eu-west-2b"]
private_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24"]
public_subnet_cidrs  = ["10.0.101.0/24", "10.0.102.0/24"]

# No NAT gateways. var.enable_nat_gateway defaults to true, which meant a dev
# apply quietly created two of them at ~$33/mo each — more than the entire prod
# environment costs. Tasks run in public subnets, SG-locked to ALB-only inbound,
# exactly as prod does.
enable_nat_gateway = false

# ECS — minimal sizing for dev
api_cpu           = 256
api_memory        = 512
api_desired_count = 1

consumer_cpu           = 256
consumer_memory        = 512
consumer_desired_count = 1

# ── Cost controls (same rationale as prod.tfvars) ────────────────────────────
# Dev is provisioned on demand and torn down again, so default to the cheapest
# shape. Each of these defaults to the expensive option in variables.tf.
enable_self_hosted_agent  = false
enable_container_insights = false
api_use_spot              = true

# SQS
sqs_visibility_timeout_seconds = 300
sqs_message_retention_seconds  = 86400 # 1 day in dev
sqs_dlq_max_receive_count      = 3

# Domain — no cert needed for dev (HTTP only via ALB DNS)
domain_name         = "dev.tekwatch.io"
acm_certificate_arn = "" # Set via GitHub secret ACM_CERT_ARN_DEV

# Same TekWatch publisher organisation boundary as production.
publisher_org_id = "o-vvi9eethqx"

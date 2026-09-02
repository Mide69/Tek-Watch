# ── Production environment configuration ─────────────────────────────────────
# Cost-minimum sizing for pre-revenue launch (~$55-90/mo). Bump
# api_desired_count/consumer_desired_count back to 2-3, restore 3 AZs, and
# set enable_nat_gateway = true once real paying-customer traffic justifies
# the HA spend — every value below is a one-line tfvars change + apply.
environment = "prod"
aws_region  = "eu-west-2"

# Must enclose the subnet ranges below. var.vpc_cidr defaults to 10.0.0.0/16
# (dev's range), so without this every prod subnet fails to create with
# InvalidSubnet.Range — the subnets sit outside the VPC they belong to.
vpc_cidr = "10.2.0.0/16"

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

consumer_cpu    = 256
consumer_memory = 512
# 0 until the first customer agent publishes. Nothing is sending to SQS yet, so
# a 24/7 poller on an empty queue is pure cost. Set back to 1 during onboarding
# — the ingest-queue alarm below is the backstop if that is forgotten.
consumer_desired_count = 0

# ~70% off the API's Fargate bill. Single task, so a Spot reclaim means a short
# gap; acceptable pre-revenue, revisit alongside api_desired_count.
api_use_spot = true

# consumer_desired_count is 0, so ANY visible message means metrics are arriving
# with nothing draining them. Alarm on the first one rather than the default
# 10,000, and after one period instead of three — SQS retention below caps how
# long the backlog survives.
ingest_queue_depth_threshold          = 0
ingest_queue_depth_evaluation_periods = 1

# ── Cost controls ────────────────────────────────────────────────────────────
# Off until the central account's own agent is actually configured. While
# TEK_WATCH_API_KEY is unset every firing launches a Fargate task that exits
# immediately with "Missing required environment variables" — ~8,700 wasted
# task launches a month. Flip back to true once the key is in Secrets Manager.
enable_self_hosted_agent = false

# Off: per-task custom metrics billed per metric, for a two-task cluster.
# CloudWatch logs and all five alarms keep working without it.
enable_container_insights = false

# SQS
sqs_visibility_timeout_seconds = 300
# 14 days (the SQS maximum), not 4. SQS bills per request, not per day retained,
# so this widens the recovery window at no cost while the consumer sits idle.
sqs_message_retention_seconds = 1209600
sqs_dlq_max_receive_count     = 3

# Registered and delegated to Cloudflare. Drives the dashboard_domain and
# admin_domain locals in main.tf, so prod serves app.tekwatch.io and
# admin.tekwatch.io. DNS is at Cloudflare, not Route 53, which is why the ACM
# validation records have to be added there by hand.
domain_name = "tekwatch.io"

# Phase 1 requests the us-east-1 cert; flip attach_custom_domain to true only
# once it reports ISSUED. See the comment on aws_acm_certificate.cloudfront.
enable_custom_domain = true
# Cert verified ISSUED (both app. and admin. validated SUCCESS) before flipping
# this — CloudFront rejects a certificate still in PENDING_VALIDATION.
attach_custom_domain = true

acm_certificate_arn = "" # ALB HTTPS listener; API is served via the CloudFront /api/* proxy for now

# Signup invites and password resets go out through SES, DKIM-signed by
# tekwatch.io, rather than Cognito's built-in sender at verificationemail.com.
# Production access was granted on 2026-08-31 (50,000/day, enforcement HEALTHY).
cognito_ses_source_arn = "arn:aws:ses:eu-west-2:409415530028:identity/tekwatch.io"
cognito_ses_from_email = "no-reply@tekwatch.io"

# Accounts in this organization may publish to the ingest queue. The previous
# condition compared aws:PrincipalOrgID to the literal "*", which StringEquals
# never matches, so no agent could publish at all.
publisher_org_id = "o-vvi9eethqx"

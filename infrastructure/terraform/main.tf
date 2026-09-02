terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  # Remote state — update bucket/key for your account
  backend "s3" {
    bucket         = "tek-watch-terraform-state"
    key            = "tek-watch/terraform.tfstate"
    region         = "eu-west-2"
    encrypt        = true
    dynamodb_table = "tek-watch-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# us-east-1 provider — needed for CloudFront ACM certs and Trusted Advisor
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  name_prefix = "${var.project}-${var.environment}"

  # Conventional per-environment subdomains. Prod dashboard already matches
  # dashboard.yml's hardcoded NEXT_PUBLIC_API_BASE_URL/login redirect target
  # (app.tekwatch.io); the rest follow the same pattern. Override by changing
  # var.domain_name per environment in environments/*.tfvars if these don't
  # match your actual DNS plan.
  dashboard_domain = var.environment == "prod" ? "app.${var.domain_name}" : "${var.environment}.${var.domain_name}"
  admin_domain     = var.environment == "prod" ? "admin.${var.domain_name}" : "admin-${var.environment}.${var.domain_name}"

  # Without a NAT gateway, ECS tasks have no private-subnet egress path, so
  # they run in public subnets with a public IP instead (still SG-locked to
  # ALB-only inbound — see modules/networking's enable_nat_gateway doc).
  ecs_task_subnet_ids = var.enable_nat_gateway ? module.networking.private_subnet_ids : module.networking.public_subnet_ids
}

# ── SNS — Ops Alerts (created before modules to avoid circular dependency) ────
# secrets needs the ARN to store it; monitoring needs it for alarms/Lambda.
# Keeping it here breaks the secrets → monitoring → ecs → secrets cycle.

resource "aws_sns_topic" "ops_alerts" {
  name = "${local.name_prefix}-ops-alerts"
  tags = { Name = "${local.name_prefix}-ops-alerts" }
}

# Every alarm in the monitoring module publishes here. With no subscription the
# topic silently swallows them, which is how this environment shipped: four
# working alarms firing into nothing. AWS emails a confirmation link on create;
# the subscription stays "pending confirmation" until it is clicked.
#
# Set via a gitignored *.auto.tfvars file rather than environments/*.tfvars —
# this repository is public and the value is a personal address.
resource "aws_sns_topic_subscription" "ops_alerts_email" {
  count     = var.ops_alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.ops_alerts.arn
  protocol  = "email"
  endpoint  = var.ops_alert_email
}

# Say so in the plan when there is no subscriber, rather than counting to zero
# in silence. The count above means a missing value does not fail the apply, it
# just produces a topic nobody is listening to — which is indistinguishable
# from a healthy platform right up until the first alarm nobody answers.
check "ops_alerts_have_a_subscriber" {
  assert {
    condition     = var.environment != "prod" || var.ops_alert_email != ""
    error_message = "ops_alert_email is empty, so the prod ops alerts topic has no subscriber. Set the OPS_ALERT_EMAIL secret (CI) or prod.secret.auto.tfvars (local)."
  }
}

# ── ACM certificate for the CloudFront custom domains ────────────────────────
# Must live in us-east-1: CloudFront only accepts certificates from that region
# no matter where the distribution or its origin sit. This is a common trip-up.
#
# Validation is DNS, and the zone for this domain is hosted at Cloudflare rather
# than Route 53, so terraform cannot create the validation records itself. It
# raises the request; the CNAMEs from the acm_validation_records output are added
# by hand at the DNS host. There is deliberately no aws_acm_certificate_validation
# resource — it would block the apply waiting on records that do not exist yet.
#
# Two-phase by design:
#   enable_custom_domain = true  -> request the cert, print the records
#   attach_custom_domain = true  -> once ISSUED, hand it to the distributions
# Attaching a cert that is still PENDING_VALIDATION fails the CloudFront update,
# so the second flag is only flipped after the first phase has validated.
resource "aws_acm_certificate" "cloudfront" {
  count    = var.enable_custom_domain ? 1 : 0
  provider = aws.us_east_1

  domain_name               = local.dashboard_domain
  subject_alternative_names = [local.admin_domain]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = "${local.name_prefix}-cloudfront-cert" }
}

locals {
  # Empty until the operator confirms the cert is ISSUED and flips
  # attach_custom_domain, which is what switches the distributions onto their
  # custom domains and their own certificate.
  cloudfront_cert_arn = (
    var.enable_custom_domain && var.attach_custom_domain
    ? aws_acm_certificate.cloudfront[0].arn
    : var.cloudfront_certificate_arn
  )
}

# ── Networking ────────────────────────────────────────────────────────────────

module "networking" {
  source = "./modules/networking"

  name_prefix          = local.name_prefix
  vpc_cidr             = var.vpc_cidr
  availability_zones   = var.availability_zones
  private_subnet_cidrs = var.private_subnet_cidrs
  public_subnet_cidrs  = var.public_subnet_cidrs
  acm_certificate_arn  = var.acm_certificate_arn
  enable_nat_gateway   = var.enable_nat_gateway
}

# ── ECR ───────────────────────────────────────────────────────────────────────

module "ecr" {
  source      = "./modules/ecr"
  name_prefix = local.name_prefix
  environment = var.environment
  # Repos are shared across environments, so they are named from the project
  # alone rather than name_prefix. See the module for why.
  project = var.project

  providers = {
    aws.us_east_1 = aws.us_east_1
  }
}

# ── DynamoDB ──────────────────────────────────────────────────────────────────

module "dynamodb" {
  source      = "./modules/dynamodb"
  name_prefix = local.name_prefix
  environment = var.environment
}

# ── SQS ───────────────────────────────────────────────────────────────────────

module "sqs" {
  source                     = "./modules/sqs"
  name_prefix                = local.name_prefix
  visibility_timeout_seconds = var.sqs_visibility_timeout_seconds
  message_retention_seconds  = var.sqs_message_retention_seconds
  dlq_max_receive_count      = var.sqs_dlq_max_receive_count

  publisher_org_id = var.publisher_org_id
}

# ── Cognito ───────────────────────────────────────────────────────────────────

module "cognito" {
  source                     = "./modules/cognito"
  name_prefix                = local.name_prefix
  environment                = var.environment
  admin_google_client_id     = var.admin_google_client_id
  admin_google_client_secret = var.admin_google_client_secret

  ses_source_arn = var.cognito_ses_source_arn
  ses_from_email = var.cognito_ses_from_email
}

# ── Secrets Manager ───────────────────────────────────────────────────────────

module "secrets" {
  source      = "./modules/secrets"
  name_prefix = local.name_prefix
  environment = var.environment

  secret_values = {
    dynamodb_customers_table       = module.dynamodb.customers_table_name
    dynamodb_alerts_table          = module.dynamodb.alerts_table_name
    dynamodb_thresholds_table      = module.dynamodb.thresholds_table_name
    dynamodb_usage_table           = module.dynamodb.usage_table_name
    dynamodb_audit_log_table       = module.dynamodb.audit_log_table_name
    dynamodb_metrics_table         = module.dynamodb.metrics_table_name
    dynamodb_events_table          = module.dynamodb.events_table_name
    cognito_customer_user_pool_id  = module.cognito.customer_user_pool_id
    cognito_customer_app_client_id = module.cognito.customer_app_client_id
    cognito_admin_user_pool_id     = module.cognito.admin_user_pool_id
    cognito_admin_app_client_id    = module.cognito.admin_app_client_id
    sns_ops_alerts_topic_arn       = aws_sns_topic.ops_alerts.arn
    sqs_ingest_queue_url           = module.sqs.ingest_queue_url
    anthropic_api_key              = var.anthropic_api_key
  }
}

# ── ECS ───────────────────────────────────────────────────────────────────────

module "ecs" {
  source      = "./modules/ecs"
  name_prefix = local.name_prefix
  environment = var.environment
  aws_region  = var.aws_region

  vpc_id                = module.networking.vpc_id
  task_subnet_ids       = local.ecs_task_subnet_ids
  assign_public_ip      = !var.enable_nat_gateway
  alb_security_group_id = module.networking.alb_security_group_id
  alb_target_group_arn  = module.networking.api_target_group_arn

  api_image_uri      = "${module.ecr.api_repository_url}:latest"
  consumer_image_uri = "${module.ecr.consumer_repository_url}:latest"
  agent_image_uri    = module.ecr.agent_repository_url

  api_cpu           = var.api_cpu
  api_memory        = var.api_memory
  api_desired_count = var.api_desired_count

  consumer_cpu           = var.consumer_cpu
  consumer_memory        = var.consumer_memory
  consumer_desired_count = var.consumer_desired_count

  agent_cpu                 = var.agent_cpu
  agent_memory              = var.agent_memory
  agent_schedule_expression = var.agent_schedule_expression
  enable_self_hosted_agent  = var.enable_self_hosted_agent
  enable_container_insights = var.enable_container_insights
  api_use_spot              = var.api_use_spot

  secrets_manager_arn       = module.secrets.secret_arn
  cognito_customer_pool_arn = module.cognito.customer_user_pool_arn

  uploads_bucket_name = aws_s3_bucket.uploads.bucket
  uploads_bucket_arn  = aws_s3_bucket.uploads.arn

  # Baked into the CloudFormation template customers download, so it has to be
  # the real registry rather than the placeholder that shipped before.
  agent_public_image_uri = "${module.ecr.agent_public_repository_uri}:latest"

  sqs_ingest_queue_arn          = module.sqs.ingest_queue_arn
  sqs_ingest_queue_url          = module.sqs.ingest_queue_url
  self_hosted_agent_api_key     = var.self_hosted_agent_api_key
  self_hosted_agent_customer_id = var.self_hosted_agent_customer_id
  sqs_dlq_arn                   = module.sqs.dlq_arn

  dynamodb_table_arns = [
    module.dynamodb.customers_table_arn,
    module.dynamodb.alerts_table_arn,
    module.dynamodb.thresholds_table_arn,
    module.dynamodb.heartbeats_table_arn,
    module.dynamodb.usage_table_arn,
    module.dynamodb.audit_log_table_arn,
    module.dynamodb.metrics_table_arn,
    # Querying a GSI is authorized against the index's own ARN, not just the
    # base table's — without this, get_7day_summary/get_last_hour/cost
    # queries (which all go through gsi_customer_time) would silently fail
    # with AccessDenied at runtime despite terraform apply succeeding.
    "${module.dynamodb.metrics_table_arn}/index/*",
    module.dynamodb.events_table_arn,
  ]
}

# ── Monitoring ────────────────────────────────────────────────────────────────

module "monitoring" {
  source      = "./modules/monitoring"
  name_prefix = local.name_prefix
  environment = var.environment
  aws_region  = var.aws_region

  ops_alerts_topic_arn      = aws_sns_topic.ops_alerts.arn
  ecs_cluster_name          = module.ecs.cluster_name
  api_service_name          = module.ecs.api_service_name
  consumer_service_name     = module.ecs.consumer_service_name
  sqs_ingest_queue_name     = module.sqs.ingest_queue_name
  sqs_dlq_name              = module.sqs.dlq_name
  dynamodb_customers_table  = module.dynamodb.customers_table_name
  dynamodb_alerts_table     = module.dynamodb.alerts_table_name
  dynamodb_heartbeats_table = module.dynamodb.heartbeats_table_name

  ingest_queue_depth_threshold          = var.ingest_queue_depth_threshold
  ingest_queue_depth_evaluation_periods = var.ingest_queue_depth_evaluation_periods
  consumer_desired_count                = var.consumer_desired_count
  alb_arn_suffix                        = module.networking.alb_arn_suffix
  api_target_group_arn_suffix           = module.networking.api_target_group_arn_suffix
}

# ── Static site hosting (dashboard + admin portal) ────────────────────────────
# certificate_arn defaults to "" (see variables.tf) — both distributions stand
# up on their default *.cloudfront.net domain with no custom alias until a
# real us-east-1 ACM cert is requested, DNS-validated, and the var is set.

module "dashboard_hosting" {
  source          = "./modules/static_site"
  name_prefix     = local.name_prefix
  site_name       = "dashboard"
  environment     = var.environment
  domain_name     = local.dashboard_domain
  certificate_arn = local.cloudfront_cert_arn

  # Serve the API under /api/* on this same distribution so the HTTPS frontend
  # can call the HTTP-only ALB without tripping browser mixed-content blocking.
  # Once api.tekwatch.io has an ACM cert the frontends can point straight at it
  # and this can be dropped by clearing the variable.
  api_origin_domain_name = module.networking.alb_dns_name
}

module "admin_hosting" {
  source          = "./modules/static_site"
  name_prefix     = local.name_prefix
  site_name       = "admin"
  environment     = var.environment
  domain_name     = local.admin_domain
  certificate_arn = local.cloudfront_cert_arn

  api_origin_domain_name = module.networking.alb_dns_name
}

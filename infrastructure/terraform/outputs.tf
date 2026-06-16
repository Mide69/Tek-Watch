output "vpc_id" {
  description = "Central account VPC ID"
  value       = module.networking.vpc_id
}

output "api_alb_dns_name" {
  description = "API ALB DNS name"
  value       = module.networking.alb_dns_name
}

output "ecr_api_repository_url" {
  description = "ECR repository URL for the API image"
  value       = module.ecr.api_repository_url
}

output "ecr_consumer_repository_url" {
  description = "ECR repository URL for the ingest consumer image"
  value       = module.ecr.consumer_repository_url
}

output "ecr_agent_repository_url" {
  description = "ECR repository URL for the agent image"
  value       = module.ecr.agent_repository_url
}

output "sqs_ingest_queue_url" {
  description = "SQS ingest queue URL (give to customers for agent config)"
  value       = module.sqs.ingest_queue_url
}

output "sqs_ingest_queue_arn" {
  description = "SQS ingest queue ARN"
  value       = module.sqs.ingest_queue_arn
}

output "timestream_database_name" {
  description = "Timestream database name"
  value       = module.timestream.database_name
}

output "dynamodb_customers_table" {
  description = "DynamoDB customers table name"
  value       = module.dynamodb.customers_table_name
}

output "dynamodb_heartbeats_table" {
  description = "DynamoDB heartbeats table name (used by silence-detector Lambda)"
  value       = module.dynamodb.heartbeats_table_name
}

output "cognito_customer_user_pool_id" {
  description = "Cognito customer user pool ID"
  value       = module.cognito.customer_user_pool_id
}

output "cognito_customer_app_client_id" {
  description = "Cognito customer app client ID (for dashboard)"
  value       = module.cognito.customer_app_client_id
}

output "cognito_admin_user_pool_id" {
  description = "Cognito admin user pool ID"
  value       = module.cognito.admin_user_pool_id
}

output "secrets_manager_arn" {
  description = "Secrets Manager secret ARN (set as SECRETS_MANAGER_SECRET_ARN env var)"
  value       = module.secrets.secret_arn
}

output "ops_alerts_topic_arn" {
  description = "SNS ops alerts topic ARN"
  value       = module.monitoring.ops_alerts_topic_arn
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.cluster_name
}

output "agent_task_family" {
  description = "Self-hosted agent ECS task definition family — TASK_FAMILY in agent.yml"
  value       = module.ecs.agent_task_family
}

# ── Static site hosting — feeds the GitHub secrets documented in GUIDE.md ────

output "dashboard_s3_bucket" {
  description = "S3 bucket for dashboard static files — set as DASHBOARD_S3_BUCKET_* secret"
  value       = module.dashboard_hosting.bucket_name
}

output "dashboard_cf_distribution_id" {
  description = "CloudFront distribution ID for dashboard — set as DASHBOARD_CF_DISTRIBUTION_* secret"
  value       = module.dashboard_hosting.cloudfront_distribution_id
}

output "dashboard_cf_domain_name" {
  description = "CloudFront default domain for dashboard (use until a custom domain/cert is set)"
  value       = module.dashboard_hosting.cloudfront_domain_name
}

output "admin_s3_bucket" {
  description = "S3 bucket for admin portal static files — set as ADMIN_S3_BUCKET_* secret"
  value       = module.admin_hosting.bucket_name
}

output "admin_cf_distribution_id" {
  description = "CloudFront distribution ID for admin portal — set as ADMIN_CF_DISTRIBUTION_* secret"
  value       = module.admin_hosting.cloudfront_distribution_id
}

output "admin_cf_domain_name" {
  description = "CloudFront default domain for admin portal (use until a custom domain/cert is set)"
  value       = module.admin_hosting.cloudfront_domain_name
}

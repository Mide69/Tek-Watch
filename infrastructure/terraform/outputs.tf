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

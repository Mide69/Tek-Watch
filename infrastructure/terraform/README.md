# Tek Watch — Terraform Infrastructure

Manages all central account AWS resources for the Tek Watch platform.

## Architecture

```
modules/
├── networking/     VPC, subnets, NAT gateways, ALB, security groups
├── ecr/            ECR repositories (agent, api, ingest-consumer)
├── dynamodb/       customers, alerts, thresholds tables
├── timestream/     metrics + events tables
├── sqs/            ingest queue + DLQ
├── cognito/        customer + admin user pools
├── secrets/        Secrets Manager secret (all config in one secret)
├── ecs/            ECS cluster, task definitions, services, IAM roles
└── monitoring/     CloudWatch alarms, SNS ops topic, silence-detector Lambda
```

## Prerequisites

- Terraform >= 1.6.0
- AWS CLI configured with admin credentials for the central account
- S3 bucket for Terraform state: `tek-watch-terraform-state`
- DynamoDB table for state locking: `tek-watch-terraform-locks`

### Create state backend (one-time)

```bash
aws s3 mb s3://tek-watch-terraform-state --region eu-west-2
aws s3api put-bucket-versioning \
  --bucket tek-watch-terraform-state \
  --versioning-configuration Status=Enabled

aws dynamodb create-table \
  --table-name tek-watch-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-west-2
```

## Usage

### Deploy dev

```bash
cd infrastructure/terraform

terraform init \
  -backend-config="key=tek-watch/dev/terraform.tfstate"

terraform plan \
  -var-file="environments/dev.tfvars" \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY" \
  -out=tfplan

terraform apply tfplan
```

### Deploy staging

```bash
terraform init \
  -backend-config="key=tek-watch/staging/terraform.tfstate"

terraform apply \
  -var-file="environments/staging.tfvars" \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY" \
  -var="acm_certificate_arn=$ACM_CERT_ARN_STAGING"
```

### Deploy prod

```bash
terraform init \
  -backend-config="key=tek-watch/prod/terraform.tfstate"

terraform plan \
  -var-file="environments/prod.tfvars" \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY" \
  -var="acm_certificate_arn=$ACM_CERT_ARN_PROD" \
  -out=tfplan-prod

# Review plan carefully before applying
terraform apply tfplan-prod
```

## Post-deployment steps

After first `terraform apply`:

1. **Note the outputs** — especially `sqs_ingest_queue_url` and `cognito_*` IDs
2. **Update `.env.local`** with the output values
3. **Push Docker images** to ECR:
   ```bash
   # Get ECR login
   aws ecr get-login-password --region eu-west-2 | \
     docker login --username AWS --password-stdin \
     $(terraform output -raw ecr_api_repository_url | cut -d/ -f1)

   # Build and push API
   docker build -t $(terraform output -raw ecr_api_repository_url):latest ./api
   docker push $(terraform output -raw ecr_api_repository_url):latest

   # Build and push ingest consumer
   docker build -t $(terraform output -raw ecr_consumer_repository_url):latest ./ingest-consumer
   docker push $(terraform output -raw ecr_consumer_repository_url):latest

   # Build and push agent
   docker build -t $(terraform output -raw ecr_agent_repository_url):latest ./agent
   docker push $(terraform output -raw ecr_agent_repository_url):latest
   ```
4. **Force ECS redeployment** after pushing images:
   ```bash
   aws ecs update-service --cluster tek-watch-dev --service api --force-new-deployment
   aws ecs update-service --cluster tek-watch-dev --service ingest-consumer --force-new-deployment
   ```
5. **Subscribe ops email to SNS topic**:
   ```bash
   aws sns subscribe \
     --topic-arn $(terraform output -raw ops_alerts_topic_arn) \
     --protocol email \
     --notification-endpoint ops@tektribe.io
   ```

## GitHub Actions Secrets Required

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM user with Terraform permissions |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret |
| `ANTHROPIC_API_KEY` | Claude API key for anomaly detection |
| `ACM_CERT_ARN_DEV` | ACM cert ARN for dev ALB |
| `ACM_CERT_ARN_STAGING` | ACM cert ARN for staging ALB |
| `ACM_CERT_ARN_PROD` | ACM cert ARN for prod ALB |
| `COGNITO_CUSTOMER_USER_POOL_ID` | From Terraform output |
| `COGNITO_CUSTOMER_APP_CLIENT_ID` | From Terraform output |
| `COGNITO_ADMIN_USER_POOL_ID` | From Terraform output |
| `COGNITO_ADMIN_APP_CLIENT_ID` | From Terraform output |
| `DASHBOARD_S3_BUCKET_DEV` | S3 bucket for dashboard static files |
| `DASHBOARD_CF_DISTRIBUTION_DEV` | CloudFront distribution ID for dashboard |
| `ADMIN_S3_BUCKET_DEV` | S3 bucket for admin portal static files |
| `ADMIN_CF_DISTRIBUTION_DEV` | CloudFront distribution ID for admin portal |

## Destroying

```bash
# Dev only — never destroy staging/prod without explicit approval
terraform destroy -var-file="environments/dev.tfvars"
```

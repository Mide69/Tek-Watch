# Tribe Watch — Deployment Guide

## Overview

Tribe Watch has three deployment targets:

| Environment | Domain | Trigger |
|-------------|--------|---------|
| `dev` | dev.tribewatch.io | Push to `main` |
| `staging` | staging.tribewatch.io | Git tag `v*.*.*` |
| `prod` | app.tribewatch.io | Manual workflow dispatch |

---

## 1. First-time Infrastructure Setup

### 1.1 Create Terraform state backend

```bash
aws s3 mb s3://tribe-watch-terraform-state --region eu-west-2
aws s3api put-bucket-versioning \
  --bucket tribe-watch-terraform-state \
  --versioning-configuration Status=Enabled

aws dynamodb create-table \
  --table-name tribe-watch-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-west-2
```

### 1.2 Deploy infrastructure (dev)

```bash
cd infrastructure/terraform

terraform init -backend-config="key=tribe-watch/dev/terraform.tfstate"

terraform apply \
  -var-file="environments/dev.tfvars" \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY"
```

### 1.3 Note outputs

```bash
terraform output sqs_ingest_queue_url      # → give to customers
terraform output cognito_customer_user_pool_id
terraform output cognito_customer_app_client_id
terraform output secrets_manager_arn
terraform output ecr_api_repository_url
terraform output ecr_consumer_repository_url
terraform output ecr_agent_repository_url
```

---

## 2. Build and Push Docker Images

```bash
# Authenticate to ECR
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ECR_BASE="$AWS_ACCOUNT.dkr.ecr.eu-west-2.amazonaws.com"
aws ecr get-login-password --region eu-west-2 | \
  docker login --username AWS --password-stdin $ECR_BASE

# API
docker build -t $ECR_BASE/tribe-watch-dev-api:latest ./api
docker push $ECR_BASE/tribe-watch-dev-api:latest

# Ingest Consumer
docker build -t $ECR_BASE/tribe-watch-dev-ingest-consumer:latest ./ingest-consumer
docker push $ECR_BASE/tribe-watch-dev-ingest-consumer:latest

# Agent
docker build -t $ECR_BASE/tribe-watch-dev-agent:latest ./agent
docker push $ECR_BASE/tribe-watch-dev-agent:latest
```

---

## 3. Configure GitHub Actions Secrets

In your GitHub repository → Settings → Secrets and variables → Actions:

```
AWS_ACCESS_KEY_ID              IAM user key
AWS_SECRET_ACCESS_KEY          IAM user secret
ANTHROPIC_API_KEY              Claude API key
ACM_CERT_ARN_DEV               ACM cert for dev ALB (eu-west-2)
ACM_CERT_ARN_STAGING           ACM cert for staging ALB
ACM_CERT_ARN_PROD              ACM cert for prod ALB
COGNITO_CUSTOMER_USER_POOL_ID  From terraform output
COGNITO_CUSTOMER_APP_CLIENT_ID From terraform output
COGNITO_ADMIN_USER_POOL_ID     From terraform output
COGNITO_ADMIN_APP_CLIENT_ID    From terraform output
DASHBOARD_S3_BUCKET_DEV        S3 bucket name for dashboard
DASHBOARD_CF_DISTRIBUTION_DEV  CloudFront distribution ID
ADMIN_S3_BUCKET_DEV            S3 bucket name for admin portal
ADMIN_CF_DISTRIBUTION_DEV      CloudFront distribution ID
```

---

## 4. Customer Agent Deployment

### 4.1 Create customer in Admin Portal

1. Log in to `admin.tribewatch.io`
2. Navigate to **Customers → New Customer**
3. Fill in name, email, tier, AWS account IDs
4. **Save the API key** — shown only once
5. Click **Download CloudFormation** to get the pre-filled template

### 4.2 Deploy in customer AWS account

```bash
aws cloudformation create-stack \
  --stack-name tribe-watch-agent \
  --template-body file://tribe-watch-agent-TT-0001.yaml \
  --parameters \
    ParameterKey=APIKey,ParameterValue=<api-key-from-step-4.1> \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-west-2
```

The agent will start collecting metrics within 5 minutes.

---

## 5. CI/CD Pipeline

### Automatic deployments

| Event | Workflow | Action |
|-------|----------|--------|
| Push to `main` (agent/) | `agent.yml` | Build + push ECR → deploy dev |
| Push to `main` (api/) | `api.yml` | Build + push ECR → deploy dev |
| Push to `main` (ingest-consumer/) | `ingest-consumer.yml` | Build + push ECR → deploy dev |
| Push to `main` (dashboard/) | `dashboard.yml` | Build → deploy S3/CloudFront dev |
| Push to `main` (admin-portal/) | `admin-portal.yml` | Build → deploy S3/CloudFront dev |
| Push to `main` (infrastructure/terraform/) | `terraform.yml` | Plan + apply dev |
| Git tag `v*.*.*` | All workflows | Deploy to staging |
| Manual dispatch | `terraform.yml` | Plan/apply/destroy any env |

### Release to staging

```bash
git tag v1.0.0
git push origin v1.0.0
```

### Release to production

Use GitHub Actions → `terraform.yml` → Run workflow → environment: prod, action: apply

---

## 6. Local Development

```bash
# Copy env file
cp .env.example .env.local
# Edit .env.local with your values

# Start all services
docker-compose up

# API:            http://localhost:8000
# API Docs:       http://localhost:8000/docs
# Dashboard:      cd dashboard && npm run dev  → http://localhost:3000
# Admin Portal:   cd admin-portal && npm run dev  → http://localhost:3001
```

---

## 7. Health Checks

```bash
# API health
curl https://api-dev.tribewatch.io/health

# ECS service status
aws ecs describe-services \
  --cluster tribe-watch-dev \
  --services api ingest-consumer \
  --query 'services[*].{name:serviceName,running:runningCount,desired:desiredCount}'

# SQS queue depth
aws sqs get-queue-attributes \
  --queue-url <ingest-queue-url> \
  --attribute-names ApproximateNumberOfMessages
```

---

## 8. Rollback

```bash
# Roll back ECS service to previous task definition
aws ecs update-service \
  --cluster tribe-watch-dev \
  --service api \
  --task-definition tribe-watch-dev-api:<previous-revision>

# Roll back Terraform
cd infrastructure/terraform
git checkout <previous-commit> -- .
terraform apply -var-file="environments/dev.tfvars"
```

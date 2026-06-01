# Tek Watch — Deployment & Testing Guide

## Overview

Tek Watch is a multi-tenant AWS cloud monitoring SaaS platform. It consists of:

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Agent** | Python 3.12, Docker/ECS | Runs in each customer's AWS account; collects metrics from 20+ services and publishes to SQS |
| **Ingest Consumer** | Python 3.12, Docker/ECS | Reads from SQS, writes to Timestream and DynamoDB |
| **API** | FastAPI, Docker/ECS | REST API with Cognito JWT auth; serves dashboard and admin portal |
| **Dashboard** | Next.js 14, Vercel/S3 | Customer-facing monitoring UI |
| **Admin Portal** | Next.js 14, Vercel/S3 | Internal portal for managing customers and billing |
| **Silence Detector** | Python Lambda | EventBridge-triggered; raises CRITICAL alerts when an agent stops heartbeating |

**Deployment environments:**

| Environment | Domain | Trigger |
|-------------|--------|---------|
| `dev` | dev.tekwatch.io | Push to `main` |
| `staging` | staging.tekwatch.io | Git tag `v*.*.*` |
| `prod` | app.tekwatch.io | Manual workflow dispatch |

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Docker Desktop | Latest | All services + LocalStack |
| Python | 3.12+ | Agent, API, ingest-consumer |
| Node.js | 18+ | Dashboard, admin portal |
| AWS CLI | v2 | Infrastructure management |
| Terraform | 1.7+ | Infrastructure-as-code |
| Git | Any | Source control |

Install Python dependencies:

```bash
pip install pytest boto3 botocore
```

---

## Repository Structure

```
tek-watch/
├── agent/                  # Customer-side metric collector
│   ├── collectors/         # 20+ service-specific collectors
│   ├── tests/              # 50 unit tests
│   └── main.py
├── api/                    # FastAPI REST API
├── ingest-consumer/        # SQS → Timestream writer
├── dashboard/              # Customer Next.js UI (port 3000)
├── admin-portal/           # Admin Next.js UI (port 3001)
├── infrastructure/
│   ├── terraform/          # All AWS infrastructure
│   │   ├── modules/        # networking, ecs, sqs, dynamodb, cognito, etc.
│   │   └── environments/   # dev.tfvars, staging.tfvars, prod.tfvars
│   └── lambda/
│       └── silence_detector/  # Heartbeat monitor Lambda
├── .github/workflows/      # CI/CD pipelines
├── docker-compose.yml      # Local dev environment
└── .env.example            # Environment variable template
```

---

## Step-by-Step Deployment Guide

This section walks through deploying TekWatch from a blank AWS account to a live production environment. Follow the phases in order on a first deployment. Subsequent deploys are fully automated via GitHub Actions.

---

### Phase 0 — Pre-Deployment Checklist

Before starting, confirm you have:

- [ ] AWS account with billing enabled and an IAM user/role with AdministratorAccess for bootstrap steps
- [ ] Registered domain (e.g. `tekwatch.io`) — can be in Route 53 or any registrar with DNS delegation
- [ ] GitHub repository with Actions enabled
- [ ] Anthropic API key (for the AI anomaly-detection feature)
- [ ] All required tools installed (see [Prerequisites](#prerequisites) above)

---

### Phase 1 — AWS OIDC & IAM Role

GitHub Actions uses OIDC to assume an IAM role — no long-lived access keys are stored.

#### Step 1.1 — Create the OIDC Identity Provider

Run once per AWS account:

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

#### Step 1.2 — Create the GitHub Actions IAM Role

Save the trust policy (replace `<ACCOUNT_ID>` and `<ORG/REPO>`):

```bash
cat > /tmp/trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:<ORG/REPO>:*"
      }
    }
  }]
}
EOF
```

Create the role and attach a permissions policy:

```bash
aws iam create-role \
  --role-name TekWatchGitHubActionsRole \
  --assume-role-policy-document file:///tmp/trust-policy.json

# For initial bootstrap, PowerUserAccess is sufficient.
# Tighten to a custom policy after infrastructure is stable.
aws iam attach-role-policy \
  --role-name TekWatchGitHubActionsRole \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess

# Save this ARN — it becomes the AWS_ROLE_ARN GitHub secret
aws iam get-role \
  --role-name TekWatchGitHubActionsRole \
  --query Role.Arn --output text
```

---

### Phase 2 — DNS & TLS Certificates

#### Step 2.1 — Confirm Hosted Zone

```bash
# If your domain is in Route 53:
aws route53 list-hosted-zones \
  --query 'HostedZones[?Name==`tekwatch.io.`].Id' \
  --output text

# If using an external registrar, create the hosted zone first:
aws route53 create-hosted-zone \
  --name tekwatch.io \
  --caller-reference $(date +%s)
# Then delegate NS records at your registrar to the values returned above.
```

#### Step 2.2 — Request ACM Certificates

One certificate per environment, all in `eu-west-2`:

```bash
# Dev
aws acm request-certificate \
  --domain-name "*.dev.tekwatch.io" \
  --subject-alternative-names "api-dev.tekwatch.io" "admin-dev.tekwatch.io" \
  --validation-method DNS \
  --region eu-west-2

# Staging
aws acm request-certificate \
  --domain-name "*.staging.tekwatch.io" \
  --subject-alternative-names "api-staging.tekwatch.io" "admin-staging.tekwatch.io" \
  --validation-method DNS \
  --region eu-west-2

# Prod
aws acm request-certificate \
  --domain-name "*.tekwatch.io" \
  --subject-alternative-names "tekwatch.io" "api.tekwatch.io" "app.tekwatch.io" "admin.tekwatch.io" \
  --validation-method DNS \
  --region eu-west-2
```

#### Step 2.3 — Validate Certificates

For each cert, retrieve its CNAME validation records and add them to Route 53:

```bash
CERT_ARN=<arn-from-above>

# Get validation records
aws acm describe-certificate \
  --certificate-arn $CERT_ARN \
  --query 'Certificate.DomainValidationOptions[].ResourceRecord'

# Add each CNAME to Route 53, then poll until ISSUED:
watch -n 30 "aws acm describe-certificate \
  --certificate-arn $CERT_ARN \
  --query Certificate.Status --output text"
```

Save all three ARNs — you'll need them in Phase 5.

---

### Phase 3 — Terraform State Backend

Create once; shared across all environments. This step requires your local AWS credentials (not GitHub Actions):

```bash
export AWS_REGION=eu-west-2

# 1. State bucket (versioned + encrypted)
aws s3 mb s3://tek-watch-terraform-state --region $AWS_REGION

aws s3api put-bucket-versioning \
  --bucket tek-watch-terraform-state \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket tek-watch-terraform-state \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

aws s3api put-public-access-block \
  --bucket tek-watch-terraform-state \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# 2. DynamoDB lock table
aws dynamodb create-table \
  --table-name tek-watch-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION
```

---

### Phase 4 — Deploy Infrastructure (Dev First)

#### Step 4.1 — Initialise Terraform

```bash
cd infrastructure/terraform

terraform init \
  -backend-config="bucket=tek-watch-terraform-state" \
  -backend-config="key=tek-watch/dev/terraform.tfstate" \
  -backend-config="region=eu-west-2" \
  -backend-config="dynamodb_table=tek-watch-terraform-locks"
```

#### Step 4.2 — Review the Plan

```bash
terraform plan \
  -var-file="environments/dev.tfvars" \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY" \
  -var="acm_certificate_arn=<ACM_CERT_ARN_DEV>"
```

Review the output carefully — confirm resources match the module list (VPC, ECS cluster, SQS queue, DynamoDB tables, Timestream database, Cognito pools, Secrets Manager secret, ECR repositories, CloudFront distributions, ALB).

#### Step 4.3 — Apply

```bash
terraform apply \
  -var-file="environments/dev.tfvars" \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY" \
  -var="acm_certificate_arn=<ACM_CERT_ARN_DEV>"
```

Expected duration: 10–15 minutes (CloudFront distributions take the longest).

#### Step 4.4 — Capture Outputs

```bash
# Save all outputs to a file for reference
terraform output -json | tee /tmp/tf-dev-outputs.json

# Key values:
terraform output ecr_api_repository_url
terraform output ecr_agent_repository_url
terraform output ecr_consumer_repository_url
terraform output ecs_cluster_name
terraform output cognito_customer_user_pool_id
terraform output cognito_customer_app_client_id
terraform output cognito_admin_user_pool_id
terraform output cognito_admin_app_client_id
terraform output sqs_ingest_queue_url
terraform output dashboard_s3_bucket
terraform output dashboard_cf_distribution_id
terraform output admin_s3_bucket
terraform output admin_cf_distribution_id
```

---

### Phase 5 — GitHub Repository Configuration

#### Step 5.1 — Create GitHub Environments

Navigate to **GitHub → repo → Settings → Environments → New environment** and create:

| Environment | Protection rules |
|---|---|
| `dev` | None — auto-approve all deployments |
| `staging` | None — auto-approve all deployments |
| `prod` | Required reviewers: add yourself and/or a team lead |

#### Step 5.2 — Add Repository-Level Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `ECR_REPOSITORY_API` | `terraform output ecr_api_repository_url` |
| `ECR_REPOSITORY_AGENT` | `terraform output ecr_agent_repository_url` |
| `ECR_REPOSITORY_INGEST` | `terraform output ecr_consumer_repository_url` |

#### Step 5.3 — Add Environment Secrets

For each environment, go to **Settings → Environments → [env] → Add secret**.

**dev secrets:**

| Secret | Value |
|---|---|
| `AWS_ROLE_ARN` | IAM role ARN from Phase 1 |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `ACM_CERT_ARN_DEV` | ACM cert ARN from Phase 2 |
| `ECS_CLUSTER_DEV` | `terraform output ecs_cluster_name` |
| `ECS_SERVICE_API_DEV` | `tek-watch-dev-api` |
| `COGNITO_CUSTOMER_USER_POOL_ID_DEV` | `terraform output cognito_customer_user_pool_id` |
| `COGNITO_CUSTOMER_APP_CLIENT_ID_DEV` | `terraform output cognito_customer_app_client_id` |
| `COGNITO_ADMIN_USER_POOL_ID_DEV` | `terraform output cognito_admin_user_pool_id` |
| `COGNITO_ADMIN_APP_CLIENT_ID_DEV` | `terraform output cognito_admin_app_client_id` |
| `DASHBOARD_S3_BUCKET_DEV` | `terraform output dashboard_s3_bucket` |
| `DASHBOARD_CF_DISTRIBUTION_DEV` | `terraform output dashboard_cf_distribution_id` |
| `ADMIN_S3_BUCKET_DEV` | `terraform output admin_s3_bucket` |
| `ADMIN_CF_DISTRIBUTION_DEV` | `terraform output admin_cf_distribution_id` |

Repeat for **staging** (suffix `_STAGING`, values from a staging Terraform run with `environments/staging.tfvars`) and **prod** (suffix `_PROD`).

---

### Phase 6 — First Code Deployment (Dev)

Push to `main` to trigger all CI/CD pipelines simultaneously:

```bash
git push origin main
```

**Watch the pipelines in GitHub → Actions.** Expected order and duration:

| Pipeline | Trigger | Duration | What it does |
|---|---|---|---|
| `Terraform Infrastructure` | terraform/ changed | ~2 min | Validate + plan + apply |
| `API CI/CD` | api/ changed | ~5 min | Test → build Docker → push ECR → deploy ECS |
| `Agent CI/CD` | agent/ changed | ~5 min | Test → build Docker → push ECR → push ECS task def |
| `Ingest Consumer CI/CD` | ingest-consumer/ changed | ~5 min | Test → build Docker → push ECR → deploy ECS |
| `Dashboard CI/CD` | dashboard/ changed | ~4 min | Lint → type-check → test → build → deploy S3/CloudFront |
| `Admin Portal CI/CD` | admin-portal/ changed | ~4 min | Lint → type-check → test → build → deploy S3/CloudFront |

If any pipeline fails, click through to the failing step — common first-run failures:
- **ECR login fails** — confirm `ECR_REPOSITORY_*` secrets are set and the IAM role has ECR permissions
- **ECS deploy fails** — confirm `ECS_CLUSTER_DEV` / `ECS_SERVICE_API_DEV` match the Terraform outputs
- **S3 sync fails** — confirm `DASHBOARD_S3_BUCKET_DEV` is correct and the role has `s3:PutObject` on that bucket

---

### Phase 7 — DNS Configuration

After the ALB and CloudFront distributions are provisioned, point your DNS records at them.

#### API (ALB)

```bash
# Get the ALB DNS name from Terraform output or ECS service
ALB_DNS=$(terraform output -raw alb_dns_name)
ALB_ZONE_ID=$(terraform output -raw alb_hosted_zone_id)

aws route53 change-resource-record-sets \
  --hosted-zone-id <YOUR_ZONE_ID> \
  --change-batch "{
    \"Changes\": [{
      \"Action\": \"UPSERT\",
      \"ResourceRecordSet\": {
        \"Name\": \"api-dev.tekwatch.io\",
        \"Type\": \"A\",
        \"AliasTarget\": {
          \"HostedZoneId\": \"$ALB_ZONE_ID\",
          \"DNSName\": \"$ALB_DNS\",
          \"EvaluateTargetHealth\": true
        }
      }
    }]
  }"
```

#### Dashboard & Admin Portal (CloudFront)

Get the CloudFront domain names:

```bash
DASH_CF_DOMAIN=$(aws cloudfront get-distribution \
  --id $(terraform output -raw dashboard_cf_distribution_id) \
  --query Distribution.DomainName --output text)

ADMIN_CF_DOMAIN=$(aws cloudfront get-distribution \
  --id $(terraform output -raw admin_cf_distribution_id) \
  --query Distribution.DomainName --output text)
```

Add CNAME records in Route 53:

| Record name | Type | Value |
|---|---|---|
| `dev.tekwatch.io` | CNAME | `<dashboard CF domain>` |
| `admin-dev.tekwatch.io` | CNAME | `<admin CF domain>` |

DNS propagation typically takes 1–5 minutes with Route 53.

---

### Phase 8 — Verify Dev Deployment

Run all checks before promoting to staging:

```bash
# 1. API health endpoint
curl -sf https://api-dev.tekwatch.io/health && echo "API OK"

# 2. Dashboard returns 200
curl -sI https://dev.tekwatch.io | head -1

# 3. Admin portal returns 200
curl -sI https://admin-dev.tekwatch.io | head -1

# 4. ECS services: running count == desired count
aws ecs describe-services \
  --cluster tek-watch-dev \
  --services tek-watch-dev-api tek-watch-dev-ingest-consumer \
  --query 'services[*].{Service:serviceName,Running:runningCount,Desired:desiredCount}' \
  --output table

# 5. SQS queue reachable (depth should be 0 on a fresh deploy)
aws sqs get-queue-attributes \
  --queue-url $(terraform output -raw sqs_ingest_queue_url) \
  --attribute-names ApproximateNumberOfMessages \
  --query Attributes.ApproximateNumberOfMessages --output text
```

All checks must pass before proceeding.

---

### Phase 9 — Promote to Staging

```bash
git tag v1.0.0
git push origin v1.0.0
```

This tag push triggers `deploy-staging` jobs in all 6 workflows automatically. Staging Terraform must have been applied separately:

```bash
cd infrastructure/terraform

terraform init \
  -reconfigure \
  -backend-config="bucket=tek-watch-terraform-state" \
  -backend-config="key=tek-watch/staging/terraform.tfstate" \
  -backend-config="region=eu-west-2" \
  -backend-config="dynamodb_table=tek-watch-terraform-locks"

terraform apply \
  -var-file="environments/staging.tfvars" \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY" \
  -var="acm_certificate_arn=<ACM_CERT_ARN_STAGING>"
```

Populate staging GitHub environment secrets from the staging Terraform outputs, then repeat Phase 8 verification against `api-staging.tekwatch.io`.

---

### Phase 10 — Promote to Production

Production deployments are **manual-only** and require reviewer approval.

#### Step 10.1 — Apply Prod Infrastructure

In GitHub → **Actions → Terraform Infrastructure → Run workflow**:
- Branch: `main`
- Environment: `prod`
- Action: `apply`

Or manually from your terminal (requires prod AWS credentials):

```bash
cd infrastructure/terraform

terraform init \
  -reconfigure \
  -backend-config="bucket=tek-watch-terraform-state" \
  -backend-config="key=tek-watch/prod/terraform.tfstate" \
  -backend-config="region=eu-west-2" \
  -backend-config="dynamodb_table=tek-watch-terraform-locks"

terraform apply \
  -var-file="environments/prod.tfvars" \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY" \
  -var="acm_certificate_arn=<ACM_CERT_ARN_PROD>"
```

#### Step 10.2 — Deploy Services to Prod

Trigger each workflow manually in order:

1. **Actions → API CI/CD → Run workflow** (branch: `main`) → approve when prompted
2. **Actions → Ingest Consumer CI/CD → Run workflow**
3. **Actions → Agent CI/CD → Run workflow**
4. **Actions → Dashboard CI/CD → Run workflow**
5. **Actions → Admin Portal CI/CD → Run workflow**

Each job waits for an approval from the reviewers configured in the `prod` GitHub environment before proceeding.

#### Step 10.3 — Verify Production

```bash
curl -sf https://api.tekwatch.io/health && echo "Prod API OK"
curl -sI https://app.tekwatch.io | head -1
curl -sI https://admin.tekwatch.io | head -1

aws ecs describe-services \
  --cluster tek-watch-prod \
  --services tek-watch-prod-api tek-watch-prod-ingest-consumer \
  --query 'services[*].{Service:serviceName,Running:runningCount,Desired:desiredCount}' \
  --output table
```

---

### Phase 11 — Onboard First Customer

See [Customer Agent Deployment](#customer-agent-deployment) below for the full flow. Summary:

1. Log in to `admin.tekwatch.io` and create a customer record
2. Download the pre-filled CloudFormation template
3. Deploy it in the customer's AWS account
4. Verify heartbeat appears in DynamoDB within 5 minutes

---

## Local Development

### 1. Initial Setup

```bash
git clone https://github.com/tektribe-ltd/tek-watch.git
cd tek-watch
cp .env.example .env.local
```

Edit `.env.local` — for local development the LocalStack defaults are sufficient. Only `ANTHROPIC_API_KEY` requires a real value if you want AI-powered alert summarisation.

### 2. Start All Services (Recommended)

```bash
docker-compose up
```

This starts:
- **LocalStack** (`localhost:4566`) — emulates SQS, DynamoDB, SNS, Cognito, Secrets Manager
- **API** (`localhost:8000`) — FastAPI with live-reload
- **Ingest Consumer** — SQS reader

```bash
# Include the Next.js frontends
docker-compose --profile frontend up

# Include the monitoring agent
docker-compose --profile agent up
```

**Ports:**

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Dashboard | http://localhost:3000 |
| Admin Portal | http://localhost:3001 |
| LocalStack | http://localhost:4566 |

### 3. Running Services Without Docker

**Agent:**

```bash
cd agent
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

export TEK_WATCH_CUSTOMER_ID=TT-0001
export TEK_WATCH_INGEST_QUEUE_URL=https://sqs.eu-west-2.amazonaws.com/.../tek-watch-ingest
export TEK_WATCH_API_KEY=your-api-key
export AWS_REGION=eu-west-2

python main.py
```

**Ingest Consumer:**

```bash
cd ingest-consumer
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py
```

**API:**

```bash
cd api
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Dashboard:**

```bash
cd dashboard
npm install
npm run dev        # http://localhost:3000
```

**Admin Portal:**

```bash
cd admin-portal
npm install
npm run dev        # http://localhost:3001
```

### 4. Demo Mode (No Auth Required)

The dashboard runs in demo mode automatically when `NEXT_PUBLIC_COGNITO_USER_POOL_ID` is a placeholder value (default in `.env.example`). All data is served from realistic mock data with time-range and region filtering.

Set `NEXT_PUBLIC_DEMO_MODE=true` to force demo mode explicitly.

### 5. LocalStack Commands

```bash
# List SQS queues
aws --endpoint-url=http://localhost:4566 sqs list-queues

# List DynamoDB tables
aws --endpoint-url=http://localhost:4566 dynamodb list-tables

# Inspect queue depth
aws --endpoint-url=http://localhost:4566 sqs get-queue-attributes \
  --queue-url http://localhost:4566/000000000000/tek-watch-ingest \
  --attribute-names ApproximateNumberOfMessages
```

---

## Testing

### Agent Unit Tests (50 tests)

```bash
cd agent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt pytest

python -m pytest tests/ -v
```

**Test coverage:**

| Test file | What it covers |
|-----------|---------------|
| `test_collectors_base.py` | BaseCollector, MetricRecord dataclass |
| `test_ec2_collector.py` | EC2 instance metrics, CPU/network |
| `test_rds_collector.py` | RDS instance inventory, storage metrics |
| `test_lambda_collector.py` | Lambda function inventory, CloudWatch metrics |
| `test_sqs_collector.py` | SQS queue depth, age, inflight messages |
| `test_sqs_publisher.py` | Batch publish to SQS, error handling |
| `test_config.py` | Config loading from environment |
| `test_region_discovery.py` | Auto-discovery of enabled AWS regions |

Run a specific test file:

```bash
python -m pytest tests/test_ec2_collector.py -v
```

Run with coverage:

```bash
python -m pytest tests/ -v --cov=. --cov-report=html
open htmlcov/index.html
```

### Silence Detector Lambda Tests (20 tests)

```bash
cd infrastructure/lambda/silence_detector
pip install pytest boto3 botocore

python -m pytest test_handler.py -v
```

**Test coverage:**

| Class | Tests |
|-------|-------|
| `TestIsSilent` | Recent/old timestamps, None, unparseable, Z-suffix |
| `TestBuildAlert` | Alert structure, deterministic ID, description content |
| `TestUpsertAlert` | DynamoDB put_item call, throttle error handling |
| `TestResolveAlert` | update_item call, ConditionalCheckFailed (no alert to resolve) |
| `TestHandler` | Silent/active customers, mixed list, missing heartbeat, empty list |

### Full Test Suite

```bash
# From repo root — run all Python tests
cd agent && python -m pytest tests/ -v ; cd ..
cd infrastructure/lambda/silence_detector && python -m pytest test_handler.py -v ; cd -
```

Expected result: **70 tests, 0 failures**.

### Dashboard Build Verification

```bash
cd dashboard
npm run build
```

A successful build (exit code 0) confirms TypeScript compilation and all page routes resolve. Note: prerender warnings for `'use client'` pages are non-fatal and expected — the app functions correctly at runtime.

### API Tests

```bash
cd api
python -m pytest -v --cov=. --cov-report=html
```

---

## Infrastructure Deployment

### First-Time Setup — Terraform State Backend

Run once, before any `terraform init`:

```bash
AWS_REGION=eu-west-2

# S3 bucket for state storage
aws s3 mb s3://tek-watch-terraform-state --region $AWS_REGION
aws s3api put-bucket-versioning \
  --bucket tek-watch-terraform-state \
  --versioning-configuration Status=Enabled

# DynamoDB table for state locking
aws dynamodb create-table \
  --table-name tek-watch-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION
```

### Deploy Infrastructure (Dev)

```bash
cd infrastructure/terraform

terraform init -backend-config="key=tek-watch/dev/terraform.tfstate"

terraform plan -var-file="environments/dev.tfvars" \
               -var="anthropic_api_key=$ANTHROPIC_API_KEY"

terraform apply -var-file="environments/dev.tfvars" \
                -var="anthropic_api_key=$ANTHROPIC_API_KEY"
```

### Capture Outputs

```bash
terraform output sqs_ingest_queue_url           # give this to each customer agent
terraform output cognito_customer_user_pool_id
terraform output cognito_customer_app_client_id
terraform output cognito_admin_user_pool_id
terraform output cognito_admin_app_client_id
terraform output ecr_api_repository_url
terraform output ecr_consumer_repository_url
terraform output ecr_agent_repository_url
```

### Infrastructure Modules

| Module | AWS Resources |
|--------|--------------|
| `networking` | VPC, subnets, security groups, NAT gateway |
| `ecs` | ECS cluster, task definitions, services, ALB |
| `sqs` | Ingest queue + DLQ |
| `dynamodb` | Customers, alerts, thresholds tables |
| `timestream` | Metrics and events time-series database |
| `cognito` | Customer and admin user pools |
| `secrets` | Secrets Manager secret for service credentials |
| `ecr` | Container image repositories (API, consumer, agent) |
| `monitoring` | CloudWatch dashboards, alarms, EventBridge rule for silence detector |

---

## Building and Pushing Docker Images

```bash
# Get ECR base URL
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ECR_BASE="$AWS_ACCOUNT.dkr.ecr.eu-west-2.amazonaws.com"

# Authenticate
aws ecr get-login-password --region eu-west-2 | \
  docker login --username AWS --password-stdin $ECR_BASE

# Build and push API
docker build -t $ECR_BASE/tek-watch-dev-api:latest ./api
docker push $ECR_BASE/tek-watch-dev-api:latest

# Build and push Ingest Consumer
docker build -t $ECR_BASE/tek-watch-dev-ingest-consumer:latest ./ingest-consumer
docker push $ECR_BASE/tek-watch-dev-ingest-consumer:latest

# Build and push Agent
docker build -t $ECR_BASE/tek-watch-dev-agent:latest ./agent
docker push $ECR_BASE/tek-watch-dev-agent:latest
```

---

## GitHub Actions Secrets Reference

All workflows use **OIDC** — no long-lived AWS keys are stored. See Phase 5 in the deployment guide above for the full setup procedure.

**Repository-level secrets** (available to all environments):

| Secret | Value |
|---|---|
| `ECR_REPOSITORY_API` | ECR URI for the API image |
| `ECR_REPOSITORY_AGENT` | ECR URI for the agent image |
| `ECR_REPOSITORY_INGEST` | ECR URI for the ingest-consumer image |

**Per-environment secrets** (set in Settings → Environments → [env] → Secrets):

| Secret | Environments | Value |
|---|---|---|
| `AWS_ROLE_ARN` | dev, staging, prod | OIDC IAM role ARN (from Phase 1) |
| `ANTHROPIC_API_KEY` | dev, staging, prod | Anthropic Claude API key |
| `ACM_CERT_ARN_DEV` | dev | ACM cert ARN for dev ALB |
| `ACM_CERT_ARN_STAGING` | staging | ACM cert ARN for staging ALB |
| `ACM_CERT_ARN_PROD` | prod | ACM cert ARN for prod ALB |
| `ECS_CLUSTER_*` | per env | ECS cluster name (`terraform output ecs_cluster_name`) |
| `ECS_SERVICE_API_*` | per env | ECS service name for the API |
| `COGNITO_CUSTOMER_USER_POOL_ID_*` | per env | From `terraform output` |
| `COGNITO_CUSTOMER_APP_CLIENT_ID_*` | per env | From `terraform output` |
| `COGNITO_ADMIN_USER_POOL_ID_*` | per env | From `terraform output` |
| `COGNITO_ADMIN_APP_CLIENT_ID_*` | per env | From `terraform output` |
| `DASHBOARD_S3_BUCKET_*` | per env | S3 bucket for dashboard static files |
| `DASHBOARD_CF_DISTRIBUTION_*` | per env | CloudFront distribution ID for dashboard |
| `ADMIN_S3_BUCKET_*` | per env | S3 bucket for admin portal |
| `ADMIN_CF_DISTRIBUTION_*` | per env | CloudFront distribution ID for admin portal |

---

## CI/CD Pipeline

### Automatic Triggers

| Event | Workflow | Action |
|-------|----------|--------|
| Push to `main` (agent/) | `agent.yml` | Test → build → push ECR → deploy ECS (dev) |
| Push to `main` (api/) | `api.yml` | Test → build → push ECR → deploy ECS (dev) |
| Push to `main` (ingest-consumer/) | `ingest-consumer.yml` | Test → build → push ECR → deploy ECS (dev) |
| Push to `main` (dashboard/) | `dashboard.yml` | Build → deploy S3/CloudFront (dev) |
| Push to `main` (admin-portal/) | `admin-portal.yml` | Build → deploy S3/CloudFront (dev) |
| Push to `main` (infrastructure/terraform/) | `terraform.yml` | Plan + apply (dev) |
| Git tag `v*.*.*` | All workflows | Deploy to staging |
| Manual dispatch | `terraform.yml` | Plan / apply / destroy any environment |

### Promoting to Staging

```bash
git tag v1.0.0
git push origin v1.0.0
```

### Promoting to Production

GitHub Actions → **terraform.yml** → **Run workflow** → set `environment: prod`, `action: apply`.

---

## Customer Agent Deployment

### Step 1 — Create Customer in Admin Portal

1. Log in to `admin.tekwatch.io`
2. Navigate to **Customers → New Customer**
3. Fill in: company name, billing email, tier, target AWS account IDs
4. **Copy the API key** — it is shown only once
5. Click **Download CloudFormation** to get the pre-filled agent template

### Step 2 — Deploy in Customer's AWS Account

```bash
aws cloudformation create-stack \
  --stack-name tek-watch-agent \
  --template-body file://tek-watch-agent-TT-0001.yaml \
  --parameters \
    ParameterKey=APIKey,ParameterValue=<api-key-from-step-1> \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-west-2
```

The agent deploys as an ECS Fargate task and begins sending metrics within 5 minutes. It publishes heartbeats to the `tek-watch-heartbeats` DynamoDB table; the Silence Detector Lambda checks these every 15 minutes and raises a CRITICAL alert if a heartbeat gap exceeds 20 minutes.

### Step 3 — Verify Agent is Running

```bash
# Check heartbeat in DynamoDB
aws dynamodb get-item \
  --table-name tek-watch-dev-heartbeats \
  --key '{"customer_id": {"S": "TT-0001"}}'

# Check ECS task logs
aws logs tail /ecs/tek-watch-agent-TT-0001 --follow
```

---

## Silence Detector Lambda

The silence detector runs on a 15-minute EventBridge schedule. It:

1. Scans the `tek-watch-heartbeats` DynamoDB table
2. For each customer: compares `last_heartbeat` timestamp to the current time
3. If the gap exceeds `SILENCE_THRESHOLD` (default: 20 minutes):
   - Creates/updates a `SILENCE-{customer_id}` alert in `tek-watch-alerts`
   - Publishes an SNS notification if `NOTIFICATION_TOPIC` is configured
4. If the agent has recovered, resolves the existing silence alert

**Environment variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `ALERTS_TABLE` | `tek-watch-alerts` | DynamoDB alerts table |
| `HEARTBEATS_TABLE` | `tek-watch-heartbeats` | DynamoDB heartbeats table |
| `SILENCE_THRESHOLD` | `20` | Minutes before raising an alert |
| `NOTIFICATION_TOPIC` | _(empty)_ | SNS topic ARN for operator notifications |
| `LOG_LEVEL` | `INFO` | CloudWatch logging level |

**Deploy the Lambda:**

```bash
cd infrastructure/lambda/silence_detector
zip -r silence_detector.zip handler.py

aws lambda create-function \
  --function-name tek-watch-silence-detector \
  --runtime python3.12 \
  --role arn:aws:iam::<account>:role/tek-watch-lambda-role \
  --handler handler.handler \
  --zip-file fileb://silence_detector.zip \
  --timeout 60 \
  --environment Variables="{ALERTS_TABLE=tek-watch-dev-alerts,HEARTBEATS_TABLE=tek-watch-dev-heartbeats}"
```

---

## Health Checks

### API

```bash
curl https://api-dev.tekwatch.io/health
# Expected: {"status": "ok", ...}
```

### ECS Services

```bash
aws ecs describe-services \
  --cluster tek-watch-dev \
  --services api ingest-consumer \
  --query 'services[*].{name:serviceName,running:runningCount,desired:desiredCount}'
```

Both `running` and `desired` counts should match.

### SQS Queue Depth

```bash
aws sqs get-queue-attributes \
  --queue-url <ingest-queue-url> \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
```

A growing `ApproximateNumberOfMessages` with zero `NotVisible` indicates the ingest consumer is not running.

### Dashboard

```bash
curl -I https://dev.tekwatch.io
# Expected: HTTP/2 200
```

---

## Rollback Procedures

### Roll Back an ECS Service

```bash
# List task definition revisions
aws ecs list-task-definitions --family-prefix tek-watch-dev-api

# Roll back to a specific revision
aws ecs update-service \
  --cluster tek-watch-dev \
  --service api \
  --task-definition tek-watch-dev-api:<previous-revision>
```

### Roll Back Terraform Changes

```bash
cd infrastructure/terraform
git checkout <previous-commit> -- .
terraform apply -var-file="environments/dev.tfvars"
```

### Roll Back a Lambda

```bash
# List published versions
aws lambda list-versions-by-function --function-name tek-watch-silence-detector

# Update the alias to point to a previous version
aws lambda update-alias \
  --function-name tek-watch-silence-detector \
  --name live \
  --function-version <previous-version>
```

---

## Extending the Agent

### Adding a New Collector

1. Create `agent/collectors/myservice.py`:

```python
"""MyService collector."""
import logging
from typing import List
from botocore.exceptions import ClientError
from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class MyServiceCollector(BaseCollector):
    SERVICE_NAME = "myservice"

    def collect(self) -> List[MetricRecord]:
        records: List[MetricRecord] = []
        try:
            client = self._session.client("myservice", region_name=self._region)
            # ... collect metrics ...
        except ClientError as exc:
            logger.error("MyService collection failed: %s", exc)
        return records
```

2. Register in `agent/main.py`:

```python
from collectors.myservice import MyServiceCollector

REGIONAL_COLLECTORS = [
    # ... existing collectors ...
    MyServiceCollector,
]
```

3. Add tests in `agent/tests/test_myservice_collector.py` following the pattern in `test_sqs_collector.py`.

### Adding an API Endpoint

1. Create `api/routers/myrouter.py`:

```python
from fastapi import APIRouter, Depends
from auth.dependencies import CustomerContext, get_current_customer

router = APIRouter()

@router.get("/my-endpoint")
async def get_my_data(customer: CustomerContext = Depends(get_current_customer)):
    return {"data": "example"}
```

2. Register in `api/main.py`:

```python
from routers import myrouter
app.include_router(myrouter.router, prefix="/api/v1/myrouter", tags=["MyRouter"])
```

---

## Code Style

### Python

- PEP 8, max 100 characters per line
- Type hints required on all function signatures
- `logging` module only — never `print()`
- Imports ordered: stdlib → third-party → local

### TypeScript (Dashboard / Admin Portal)

- Strict mode enabled
- Function components only
- Absolute imports via `@/` prefix
- Tailwind CSS for styling

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Agent can't publish to SQS | Wrong queue URL or missing IAM permissions | Check `TEK_WATCH_INGEST_QUEUE_URL`; verify `sqs:SendMessage` IAM policy |
| API returns 401 Unauthorized | Expired or invalid JWT | Verify Cognito pool IDs; re-authenticate |
| Dashboard shows no data | API unreachable | Check `NEXT_PUBLIC_API_BASE_URL`; confirm API health endpoint returns 200 |
| Ingest consumer not processing | SQS consumer not running | Check ECS task status; inspect CloudWatch logs |
| Timestream write fails | Missing permissions or table doesn't exist | Check IAM policy; run `terraform apply` to ensure table exists |
| Silence alert not resolving | Agent restarted but alert is stale | Silence detector runs every 15 min; wait or invoke Lambda manually |
| `ConditionalCheckFailedException` in silence detector | Alert didn't exist when resolve was attempted | Benign — logged at DEBUG, handler continues normally |

### Viewing Logs

```bash
# Docker Compose (local)
docker-compose logs -f api
docker-compose logs -f ingest-consumer
docker-compose logs --tail=100 agent

# CloudWatch (production)
aws logs tail /ecs/tek-watch-api --follow
aws logs tail /ecs/tek-watch-ingest-consumer --follow
aws logs tail /ecs/tek-watch-agent-TT-0001 --follow
aws logs tail /aws/lambda/tek-watch-silence-detector --follow
```

### VS Code Launch Configurations

Add to `.vscode/launch.json` for local debugging:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Agent",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/agent/main.py",
      "console": "integratedTerminal",
      "env": {
        "TEK_WATCH_CUSTOMER_ID": "TT-0001",
        "TEK_WATCH_INGEST_QUEUE_URL": "http://localhost:4566/000000000000/tek-watch-ingest",
        "TEK_WATCH_API_KEY": "test-key",
        "AWS_ENDPOINT_URL": "http://localhost:4566"
      }
    },
    {
      "name": "API",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--reload"],
      "cwd": "${workspaceFolder}/api"
    }
  ]
}
```

---

## Useful Commands Reference

```bash
# Format Python code
black agent/ api/ ingest-consumer/

# Lint Python code
flake8 agent/ api/ ingest-consumer/

# Type check Python code
mypy agent/ api/ ingest-consumer/

# Run full test suite
cd agent && python -m pytest tests/ -v && cd ..
cd infrastructure/lambda/silence_detector && python -m pytest test_handler.py -v && cd -

# Build dashboard
cd dashboard && npm run build

# Clean up Docker
docker-compose down -v
docker system prune -a

# Trigger silence detector manually (testing)
aws lambda invoke \
  --function-name tek-watch-silence-detector \
  --payload '{}' \
  response.json && cat response.json
```

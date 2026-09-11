# Tek Watch

> AI-assisted cloud infrastructure monitoring platform by Tek Tribe Ltd.

Tek Watch gives each Tek Tribe managed service customer a real-time, authenticated window into the state of their AWS infrastructure.

## Architecture

```
Customer AWS Account
  └── ECS Fargate (tek-watch-agent) ──HTTPS──▶ SQS (ingest queue)
                                                        │
                                          Tek Watch Central Account
                                                        │
                                              ECS (ingest-consumer)
                                                        │
                                        DynamoDB (metrics + events, TTL)
                                                        │
                                              ECS (tek-watch-api)
                                                   │         │
                                            dashboard/   admin-portal/
                                         app.tekwatch  admin.tekwatch
                                               .io            .io
```

## What is our code, and what is Claude

Every monitoring decision (what is anomalous, what fails a check, what counts
as an incident) is made by TekWatch's own deterministic code. The Claude API is
used for language only, never to decide what is wrong.

| Capability | Where it runs | How it works |
|---|---|---|
| Data collection | Our agent (`agent/collectors/`) | 23 read-only boto3 collectors, every 5 minutes |
| Baselines | Our API (`api/services/timestream.py`) | 7-day mean, standard deviation and sample count per resource metric |
| Anomaly detection | Our API (`api/services/alerting/detector.py`) | z-score against the 7-day baseline (3σ medium, 5σ high), plus step-change detection for metrics that are normally flat. Needs 24 hours and 12 samples of history first |
| Threshold alerts | Our API (`api/services/alerting/threshold.py`) | Default or customer thresholds, every 5 minutes |
| Compliance checks | Our API (`api/services/compliance.py`) | 10 rule-based checks (S3, IAM, ACM, GuardDuty, CloudTrail) mapped to UK GDPR, Cyber Essentials and ISO 27001:2022. A check with no data is reported as not measured and left out of the score, never counted as a pass |
| Incident correlation | Our API (`api/services/correlation.py`) | Joins CloudTrail changes to current S3 and trail state: who changed what and when, the UK GDPR impact, and ordered remediation |
| Alert delivery | Our API (`api/services/notifications.py`) | Email (SES) and Slack, filtered by each customer's minimum severity |
| Alert wording | Claude API, optional | Rewrites anomalies the detector already found in plain English. It cannot add, remove or re-grade them. Without a key, built-in wording is used and detection runs unchanged |
| AI assistant | Claude API | Answers questions by calling our API's tools over the customer's own data |

Compliance results are automated evidence about AWS technical controls. They
are not a certification, an audit or legal advice. FCA PS21/3 operational
resilience is not covered: it depends on business services and impact
tolerances that cannot be judged from AWS configuration.

## Repository Structure

```
tek-watch/
├── agent/                  # Python Docker agent (runs in customer account)
├── ingest-consumer/        # FastAPI SQS consumer → DynamoDB writer
├── api/                    # FastAPI central API (serves dashboards)
├── dashboard/              # Next.js customer dashboard (app.tekwatch.io)
├── admin-portal/           # Next.js admin portal (admin.tekwatch.io)
├── infrastructure/
│   ├── terraform/          # Tek Watch central account resources
│   └── cloudformation/     # Customer agent deployment template
├── .github/workflows/      # CI/CD pipelines
└── docker-compose.yml      # Local development
```

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.12+ (for local development without Docker)
- Node.js 18+ (for dashboard development)
- AWS CLI configured (for deployment)

### Local Development

1. **Clone the repository**
```bash
git clone https://github.com/Mide69/Tek-Watch.git
cd Tek-Watch
```

2. **Set up environment variables**
```bash
cp .env.example .env.local
# Edit .env.local with your configuration
```

3. **Start services with Docker Compose**
```bash
docker-compose up
```

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| LocalStack | http://localhost:4566 |

4. **Run agent manually (optional)**
```bash
docker-compose --profile agent up agent
```

### Running Individual Services

#### Agent
```bash
cd agent
pip install -r requirements.txt
python main.py
```

#### Ingest Consumer
```bash
cd ingest-consumer
pip install -r requirements.txt
python main.py
```

#### API
```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload
```

## Tech Stack

| Layer | Technology |
|---|---|
| Agent | Python 3.12, boto3 |
| Ingest Consumer | Python 3.12, FastAPI |
| API | Python 3.12, FastAPI, Anthropic SDK |
| Dashboard | Next.js 14, TypeScript, Tailwind, Shadcn/ui, SWR |
| Admin Portal | Next.js 14, TypeScript, Tailwind, Shadcn/ui, SWR |
| Metrics Store | Amazon DynamoDB (metrics + events tables, 90-day TTL) |
| App Data | Amazon DynamoDB |
| Queue | Amazon SQS |
| Auth | AWS Cognito |
| Compute | AWS ECS Fargate |
| Region | eu-west-2 (London) |

## Project Status

Live in production on AWS (eu-west-2), serving from `app.tekwatch.io`.

### Built and deployed
- [x] Agent with multi-region discovery and **23 collectors** — EC2, RDS, Lambda,
      ECS, EKS, S3, DynamoDB, ELB, VPC, Route53, CloudFront, ElastiCache, SNS,
      SQS, ACM, IAM, GuardDuty, Security Hub, Config, CloudTrail, CloudWatch
      Alarms, Cost Explorer, Trusted Advisor
- [x] SQS publisher with batching; ingest consumer writing to DynamoDB
- [x] FastAPI service with Cognito JWT auth and all customer/admin routers
- [x] Threshold alerting, statistical anomaly detection, compliance checks and
      incident correlation (our code); plain-English alert wording and the chat
      assistant (Claude API)
- [x] Customer alert delivery by email and Slack, per notification preferences
- [x] Agent silence-detection Lambda on a 10-minute EventBridge schedule
- [x] Customer dashboard and admin portal (Next.js static exports on
      S3 + CloudFront), both with password reset and TOTP MFA enrolment
- [x] Terraform for the whole central account; CloudFormation template for the
      customer-side agent
- [x] **370 automated tests** — 216 agent, 94 API, 22 Lambda, 28 dashboard,
      10 admin portal, plus Playwright end-to-end suites

### Known gaps
- [ ] **No customer data has ever flowed through the platform.** The pipeline
      (agent -> SQS -> consumer -> DynamoDB -> API -> dashboard) has never
      carried a message end to end; dashboards render mock data. Onboarding the
      first customer is the outstanding milestone.
- [ ] The ALB serves HTTP; browsers reach the API over HTTPS via a CloudFront
      `/api/*` behaviour. A dedicated `api.tekwatch.io` certificate would let
      the frontends address it directly.
- [ ] No staging environment provisioned. `staging.tfvars` is ready but unused.
- [ ] `deploy-dev` and `deploy-staging` are gated behind `ENABLE_DEV_DEPLOY` /
      `ENABLE_STAGING_DEPLOY`, both unset, because neither environment exists.
- [ ] The GitHub Actions IAM role holds `AdministratorAccess`. The OIDC trust
      condition limits it to this repository, but it should be scoped down.
- [ ] Several pinned Actions still target Node 20, which GitHub has deprecated.
      They run (forced onto Node 24) but should be bumped.

### CI/CD
Enabled via the `ENABLE_CD` repository variable. Pushes to `main` build and push
images to ECR; production deploys are `workflow_dispatch` only. Verified
deploying to prod on 30 Aug 2026.

Terraform deliberately does **not** manage the running task definition revision
(`ignore_changes`), because CD owns it — otherwise any `terraform apply` would
roll the service back to whatever revision terraform last created.

## Deployment

### Customer Agent Deployment

1. **Admin creates customer in Admin Portal**
   - Generates Customer ID (e.g., TT-0042)
   - Generates API key
   - Downloads pre-filled CloudFormation template

2. **Deploy CloudFormation stack in customer AWS account**
```bash
aws cloudformation create-stack \
  --stack-name tek-watch-agent \
  --template-body file://customer-agent-template.yaml \
  --parameters \
    ParameterKey=CustomerID,ParameterValue=TT-0042 \
    ParameterKey=IngestQueueURL,ParameterValue=https://sqs.eu-west-2.amazonaws.com/... \
    ParameterKey=APIKey,ParameterValue=your-api-key \
  --capabilities CAPABILITY_NAMED_IAM
```

3. **Agent begins collecting metrics every 5 minutes**

### Central Platform Deployment

See `infrastructure/terraform/README.md` for Terraform deployment instructions.

## API Endpoints

### Customer Endpoints (JWT Required)
- `GET /api/v1/overview` - Dashboard summary
- `GET /api/v1/compute/ec2` - EC2 instances
- `GET /api/v1/compute/lambda` - Lambda functions
- `GET /api/v1/databases/rds` - RDS instances
- `GET /api/v1/security/guardduty` - GuardDuty findings
- `GET /api/v1/security/compliance` - Automated compliance check results
- `GET /api/v1/security/incidents` - Correlated security incidents
- `GET|PUT /api/v1/notifications/preferences` - Email, Slack and minimum severity
- `GET /api/v1/cost/summary` - Cost overview
- `GET /api/v1/alerts` - Active alerts
- `GET /api/v1/metrics/{resource_id}` - Time-series data
- `GET /api/v1/profile` - Company profile (name, address, logo)
- `PUT /api/v1/profile` - Update company profile
- `POST /api/v1/profile/logo` - Upload a company logo (PNG/JPEG/GIF, max 2 MB)
- `DELETE /api/v1/profile/logo` - Remove the company logo

### Admin Endpoints (Admin JWT Required)
- `GET /api/v1/admin/customers` - List all customers
- `POST /api/v1/admin/customers` - Create customer
- `PUT /api/v1/admin/customers/{id}` - Update customer
- `POST /api/v1/admin/customers/{id}/rotate-key` - Rotate API key
- `GET /api/v1/admin/thresholds` - Manage thresholds
- `GET /api/v1/admin/operations` - Platform health

## Configuration

### Environment Variables

See `.env.example` for all configuration options.

**Required for Agent:**
- `TEK_WATCH_CUSTOMER_ID`
- `TEK_WATCH_INGEST_QUEUE_URL`
- `TEK_WATCH_API_KEY`

**Required for API/Consumer:**
- `AWS_REGION`
- `ENVIRONMENT`
- `SECRETS_MANAGER_SECRET_ARN` (production) or individual env vars (dev)

### Secrets Manager Structure

Production deployments use AWS Secrets Manager:
```json
{
  "dynamodb_customers_table": "tek_watch_customers",
  "dynamodb_metrics_table": "tek_watch_metrics",
  "dynamodb_events_table": "tek_watch_events",
  "cognito_customer_user_pool_id": "...",
  "anthropic_api_key": "...",
  "sns_ops_alerts_topic_arn": "..."
}
```

## Development Guidelines

### Code Style
- Python: PEP 8, max line length 100, type hints required
- TypeScript: Strict mode, no `any` types
- All functions must have docstrings (Google style)

### Testing
```bash
# Agent tests
cd agent && pytest

# API tests
cd api && pytest --cov=. --cov-fail-under=70

# Dashboard tests
cd dashboard && npm test
```

### Logging
- Use structured JSON logging
- Never use `print()` in production code
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

## Security

- All secrets stored in AWS Secrets Manager
- API keys hashed with SHA-256
- JWT tokens expire after 8 hours
- Admin portal requires MFA
- Customer data isolated by `customer_id` in all queries
- Agent has read-only IAM permissions

## Monitoring

- CloudWatch Logs for all services
- CloudWatch Alarms for DLQ depth, API errors, ECS failures
- Agent silence detection (alerts if no heartbeat > 20 min)
- Platform health dashboard in Admin Portal

## Contributing

1. Create a feature branch from `main`
2. Make changes following code style guidelines
3. Add tests for new functionality
4. Submit PR with clear description
5. Ensure CI passes

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Deployment & Testing Guide](docs/GUIDE.md)
- [Runbook](docs/RUNBOOK.md)
- [Zero-cost demo deployment](docs/DEMO_DEPLOYMENT.md)

## License

Proprietary. Copyright © 2026 Tek Tribe Ltd. All rights reserved.
See [LICENSE](LICENSE).

## Support

For issues or questions:
- Internal: Slack #tek-watch
- Customers: support@tekwatch.io

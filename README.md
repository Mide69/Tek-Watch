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
git clone https://github.com/tektribe-ltd/tek-watch.git
cd tek-watch
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
| Metrics Store | Amazon DynamoDB (metrics + events tables, TTL) |
| App Data | Amazon DynamoDB |
| Queue | Amazon SQS |
| Auth | AWS Cognito |
| Compute | AWS ECS Fargate |
| Region | eu-west-2 (London) |

## Project Status

### ✅ Completed
- [x] Agent framework with multi-region discovery
- [x] Collectors: EC2, Lambda, RDS, SQS, GuardDuty, ACM, IAM, Cost Explorer, CloudWatch Alarms
- [x] SQS publisher with batching
- [x] Ingest consumer with validation and DynamoDB writer
- [x] API framework with Cognito JWT authentication
- [x] All API routers (overview, compute, databases, networking, storage, messaging, security, cost, alerts, agent, metrics)
- [x] Admin routers (customers, thresholds, operations)
- [x] DynamoDB service layer
- [x] DynamoDB-backed metrics query service
- [x] Threshold alerting engine
- [x] AI anomaly detection with Claude
- [x] Notification service (SNS)
- [x] Dockerfiles for all services
- [x] CloudFormation template for customer deployment
- [x] GitHub Actions CI/CD workflows
- [x] Docker Compose for local development

### 🚧 In Progress / TODO
- [ ] Dashboard (Next.js customer-facing UI)
- [ ] Admin Portal (Next.js admin UI)
- [ ] Terraform modules for central infrastructure
- [ ] Additional collectors (ECS, ElastiCache, VPC, ELB, CloudFront, Route53, SNS, DynamoDB, Security Hub, Config, Trusted Advisor)
- [ ] Unit tests for all components
- [ ] Integration tests
- [ ] Agent silence detection Lambda
- [ ] Complete documentation

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
- `GET /api/v1/cost/summary` - Cost overview
- `GET /api/v1/alerts` - Active alerts
- `GET /api/v1/metrics/{resource_id}` - Time-series data

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

- [Requirements](.kiro/specs/requirements.md)
- [System Design](.kiro/specs/design.md)
- [User Stories](.kiro/specs/stories.md)
- [Steering](.kiro/specs/steering.md)

## License

Proprietary - Tek Tribe Ltd © 2026

## Support

For issues or questions:
- Internal: Slack #tek-watch
- Customers: support@tektribe.io

# Tek Watch — Architecture

## System Overview

Tek Watch is a **multi-tenant SaaS** AWS infrastructure monitoring platform. Each customer deploys a lightweight Fargate agent into their AWS account; the agent ships telemetry to a central Tek Tribe-owned AWS account where it is stored, analysed, and surfaced through the dashboard.

```
┌─────────────────────────────────────────────────────────────┐
│  Customer AWS Account                                        │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Tek Watch Agent (ECS Fargate — scheduled, 5 min)   │   │
│  │  • 25 collectors: EC2, RDS, Lambda, ECS, S3, SQS …  │   │
│  │  • Reads via ReadOnly IAM + Cost Explorer            │   │
│  │  • Sends JSON batches → SQS Ingest Queue            │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────┘
                             │ SQS SendMessage
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  Tek Tribe Central AWS Account (eu-west-2 primary)          │
│                                                             │
│  SQS Ingest Queue                                           │
│       │                                                     │
│       ▼                                                     │
│  ECS Ingest Consumer ───────► DynamoDB (metrics/events, TTL)│
│                               DynamoDB (customers/alerts)   │
│                                                             │
│  FastAPI (ECS Fargate)                                      │
│  ├── /api/v1/...          Customer dashboard API            │
│  ├── /api/v1/admin/...    Admin management API              │
│  ├── /api/v1/chat         Claude AI agentic chat            │
│  ├── /api/v1/notifications Notification preferences         │
│  ├── Background: threshold evaluation loop (60s)            │
│  └── Background: AI anomaly detection loop (5 min)          │
│                                                             │
│  Next.js Dashboard (S3 + CloudFront)                        │
│  Next.js Admin Portal (S3 + CloudFront)                     │
│                                                             │
│  Cognito (2 pools: customer + admin)                        │
│  SNS ops-alerts topic → Tek Tribe on-call                   │
│  SES → customer alert emails                                │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Telemetry Ingestion
1. Agent runs on a schedule (default: every 5 min) inside the customer's AWS account
2. Agent collects metrics from 25 AWS services via boto3 ReadOnly calls
3. Metrics are batched and sent to the Tek Watch SQS ingest queue in the central account
4. ECS ingest consumer (Fargate) consumes the SQS messages, fans out to:
   - **DynamoDB metrics + events tables (TTL)** — time-series metrics (CPU, memory, latency, cost trend) and string-valued events
   - **DynamoDB** — resource inventory, alert state, customer metadata

### Alert Evaluation
The API runs two background workers:

| Worker | Interval | Purpose |
|--------|----------|---------|
| `threshold_evaluation_loop` | 60 s | Reads customer thresholds from DynamoDB, queries the metrics table for latest values, fires alerts when breached |
| `anomaly_detection_loop` | 5 min | Sends metrics to Claude for AI-powered anomaly detection, creates AI-flagged alerts |

When an alert fires:
- Alert is written to DynamoDB (`tek_watch_alerts` table)
- SNS ops-alerts topic is notified (Tek Tribe internal)
- If customer has `email_enabled=true` in notification preferences: SES email sent
- If customer has `slack_webhook_url` set: Slack webhook POSTed

### Real-Time Push
The `/api/v1/alerts/stream` endpoint serves **Server-Sent Events (SSE)**. The dashboard can connect with `EventSource` to receive active-alert pushes every 30 seconds without polling.

---

## Authentication & Multi-Tenancy

```
Customer Login
  │
  ▼
Cognito Customer User Pool
  │ JWT (sub = customer_id)
  ▼
FastAPI → get_current_customer() → CustomerContext(customer_id)
  │
  └── All DynamoDB queries scoped to customer_id (partition key)
      All metrics/events queries are scoped by customer_id
```

- **Customer JWT** → `CustomerContext` — used on all `/api/v1/...` endpoints
- **Admin JWT** → `AdminContext` — used on all `/api/v1/admin/...` endpoints
- There is **no cross-customer data leakage** possible at the query layer; `customer_id` is always sourced from the verified JWT, never from request parameters

---

## DynamoDB Tables

| Table | PK | SK | Purpose |
|-------|----|----|---------|
| `tek_watch_customers` | `customer_id` | — | Customer profiles, API keys, notification prefs |
| `tek_watch_alerts` | `customer_id` | `alert_id` | Alert records; GSI on `status` |
| `tek_watch_thresholds` | `customer_id` | `threshold_id` | Customer-defined metric thresholds |

---

## API Security

| Control | Implementation |
|---------|---------------|
| Auth | Cognito JWT verified on every request (`python-jose`) |
| Rate limiting | `slowapi` — 200 req/min global; 10 req/min on `/chat` |
| CORS | Allowed origins from `ALLOWED_ORIGINS` env var (never hardcoded) |
| Security headers | `SecurityHeadersMiddleware` — X-Content-Type-Options, X-Frame-Options, CSP, HSTS, Referrer-Policy |
| Secrets | AWS Secrets Manager in prod; environment vars in dev |
| CI/CD | GitHub Actions OIDC — no long-lived AWS keys |
| Input validation | Pydantic v2 models on all request bodies |

---

## Frontend Architecture

```
dashboard/
├── src/app/                  Next.js 14 App Router pages
│   ├── overview/             KPI cards, cost trend, top CPU
│   ├── compute/              EC2 / Lambda / ECS tabs
│   ├── alerts/               Paginated alert list, SSE, CSV export
│   ├── cost/                 Cost summary, service breakdown
│   ├── chat/                 Claude AI natural-language queries
│   └── ...                   databases, networking, storage, messaging, security
├── src/components/
│   ├── layout/DashboardLayout.tsx   Sidebar, header, toast, ErrorBoundary
│   └── ui/                   Card, Badge, Skeleton, MiniChart, ThemeToggle,
│                             NotificationBell, ErrorBoundary
├── src/hooks/useData.ts      SWR data hooks — 4s timeout, mock fallback
├── src/contexts/
│   ├── DashboardContext.tsx  Time range, region, refresh, toast state
│   └── ThemeContext.tsx      dark/light theme — persisted to localStorage
└── src/lib/
    ├── api.ts                Typed API client (axios)
    └── mockData.ts           Rich time-range-aware mock data
```

### Theming
- CSS custom properties (`--background`, `--foreground`, `--primary`, …) defined in `globals.css`
- `:root` = light theme; `.dark` = dark theme
- `ThemeProvider` toggles `.dark` class on `<html>` and persists to `localStorage`
- Tailwind configured with all custom colours supporting `<alpha-value>` for opacity modifiers

---

## Infrastructure (Terraform)

```
infrastructure/
├── modules/
│   ├── networking/    VPC, subnets, NAT, security groups
│   ├── compute/       ECS cluster, Fargate task definitions
│   ├── data/          DynamoDB (incl. metrics/events), S3
│   ├── auth/          Cognito user pools
│   ├── messaging/     SQS, SNS
│   └── cdn/           CloudFront, ACM
└── environments/
    ├── dev/
    ├── staging/
    └── prod/
```

Remote state: S3 bucket + DynamoDB lock table per environment.

---

## Deployment

See [GUIDE.md](GUIDE.md) for step-by-step deployment instructions.

| Environment | Trigger | Approvals |
|-------------|---------|-----------|
| dev | Push to `develop` | None |
| staging | Push to `staging` | None |
| prod | Push to `main` | Manual approval gate |

---

## ADRs (Architecture Decision Records)

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | FastAPI over Django REST | Async-first; lighter weight; native Pydantic v2 |
| 2 | DynamoDB for metrics/events (was Timestream) | Amazon Timestream for LiveAnalytics closed to new AWS customers on 2025-06-20, so it cannot be provisioned on a new account. Replaced with two purpose-shaped DynamoDB tables (metrics keyed `customer_id#resource_id#metric_name` + a `customer_id`-time GSI; events keyed `customer_id#service`), both with per-item TTL. Same serverless, single-digit-ms, AWS-native profile; aggregation done in the query service. |
| 3 | DynamoDB for state | Serverless; single-digit ms at any scale; per-item TTL |
| 4 | Claude for AI features | Best-in-class reasoning; native tool-use for multi-step queries |
| 5 | Next.js App Router | RSC for static data; client components only where needed |
| 6 | Cognito for auth | Managed JWT; OIDC-compliant; no custom auth code to maintain |
| 7 | slowapi for rate limiting | Zero-dependency FastAPI integration; in-memory for single instance |
| 8 | SSE over WebSocket | Simpler infrastructure; unidirectional push sufficient for alert feeds |

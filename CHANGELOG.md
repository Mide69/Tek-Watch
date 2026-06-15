# Changelog

All notable changes to Tek Watch are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- AI Chat feature: natural-language infrastructure queries via Claude tool-use agentic loop (10 tools)
- Dark/light theme toggle persisted to `localStorage`; smooth CSS variable transitions
- Rate limiting: 200 req/min global default via `slowapi`; 10 req/min on `/chat`
- Security response headers: X-Content-Type-Options, X-Frame-Options, CSP, HSTS, Referrer-Policy
- Paginated `/api/v1/alerts` endpoint with `limit` and `offset` query params
- SSE endpoint `/api/v1/alerts/stream` for real-time alert push
- CSV/JSON export endpoint `/api/v1/alerts/export`
- Customer notification preferences endpoint (`GET/PUT /api/v1/notifications/preferences`)
- SES email notifications for customer alerts
- Slack webhook integration for customer alert delivery
- Notification bell in dashboard header with live active-alert count
- React `ErrorBoundary` component wrapping `DashboardLayout`
- Pagination controls on Alerts page
- CSV export download button on Alerts page
- Semantic Tailwind colour tokens throughout all pages (light-mode compatible)
- Empty states on Compute, Databases, Storage, Networking, Messaging pages
- Admin portal: pagination on customer list endpoint
- Admin portal: per-customer CloudFormation template download
- Pre-commit hooks (ruff, mypy, ESLint, tsc, standard file checks)
- Per-service `.env.example` files
- Architecture documentation at `docs/ARCHITECTURE.md`
- Deployment guide at `docs/GUIDE.md`

### Changed
- CORS allowed origins now loaded from `ALLOWED_ORIGINS` env var / Secrets Manager instead of hardcoded localhost
- Error responses normalised to `{"error": {"code": "...", "message": "...", "details": {...}}}` across all endpoints
- `useAlerts` hook returns `{alerts, total, limit, offset}` instead of a bare array
- Overview page no longer shows hardcoded customer name; uses authenticated customer ID

### Fixed
- `mockData.ts`: circular initialisation error — `MOCK_ALERTS` referenced before declaration at line 86
- `tailwind.config.js`: custom colours missing `<alpha-value>` placeholder broke opacity modifiers (e.g. `bg-primary/10`)
- `layout.tsx`: hardcoded `className="dark"` on `<html>` caused hydration mismatch with ThemeProvider

### Security
- Removed hardcoded development origins from production CORS config
- Added `detect-private-key` pre-commit hook to prevent accidental secret commits

---

## [1.0.0] — 2026-05-01

### Added
- Multi-tenant SaaS architecture: Cognito JWT auth, per-customer DynamoDB isolation
- 11-page dashboard: Overview, Compute, Databases, Networking, Storage, Messaging, Security, Cost, Alerts, Agent, Chat
- Threshold evaluation loop with DynamoDB-backed alert storage
- AI anomaly detection loop (Claude-powered)
- CloudFormation agent template auto-generated per customer
- GitHub Actions CI/CD with OIDC (no long-lived keys)
- Terraform multi-environment infrastructure (dev / staging / prod)
- Admin portal: customer CRUD, threshold management, operations view
- Tek Watch collector agent: 25 AWS service collectors
- Full test suite (unit + integration, pytest-cov)

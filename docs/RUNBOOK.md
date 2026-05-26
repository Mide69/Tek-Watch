# TekWatch Operations Runbook

## On-call contacts

| Role | Contact |
|---|---|
| Platform on-call | ops-alerts SNS topic → PagerDuty |
| Escalation | Tek Tribe engineering Slack |

---

## Health checks

### API
```bash
curl https://api.tekwatch.io/health
curl https://api-dev.tekwatch.io/health
```

### Agent (per customer)
The agent runs as an ECS Scheduled Task. Check the most recent task execution:
```bash
aws ecs list-tasks --cluster tek-watch-<env> --family tek-watch-agent
aws ecs describe-tasks --cluster tek-watch-<env> --tasks <task-arn>
```

### Ingest consumer
```bash
aws ecs describe-services \
  --cluster tek-watch-<env> \
  --services tek-watch-ingest-consumer
```

---

## Runbooks by alert type

### SQS queue depth high (`IngestQueueDepth > 1000`)

1. Check ingest-consumer ECS service is running and healthy (see above).
2. Check CloudWatch logs for consumer errors:
   ```bash
   aws logs tail /ecs/tek-watch-ingest-consumer --follow
   ```
3. Check Timestream write capacity — look for `RejectedRecords` in consumer logs.
4. If consumer is crashing: check the ECR image tag matches the deployed task definition.
5. Scale up the consumer service if processing is too slow:
   ```bash
   aws ecs update-service --cluster tek-watch-<env> \
     --service tek-watch-ingest-consumer --desired-count 2
   ```

### API 5xx error rate elevated

1. Check API ECS service logs:
   ```bash
   aws logs tail /ecs/tek-watch-api --follow
   ```
2. Check DynamoDB throttling metrics in CloudWatch.
3. Check Timestream query latency.
4. Roll back if a recent deploy caused the spike:
   ```bash
   # Redeploy previous task definition revision
   aws ecs update-service --cluster tek-watch-<env> \
     --service tek-watch-api \
     --task-definition tek-watch-api:<previous-revision>
   ```

### Agent not reporting (no metrics for > 2 collection cycles)

1. Check the customer's ECS Scheduled Task last execution status.
2. Verify the customer's IAM role (`TekWatchAgentRole`) trust policy is intact.
3. Verify the SQS queue URL in the agent's Secrets Manager secret is correct.
4. Test manually by triggering the scheduled task:
   ```bash
   aws ecs run-task --cluster tek-watch-<env> \
     --task-definition tek-watch-agent-<customer-id> \
     --launch-type FARGATE \
     --network-configuration "awsvpcConfiguration={subnets=[<subnet>],securityGroups=[<sg>]}"
   ```

### ACM certificate expiring

GuardDuty/ACM collector emits `days_until_expiry`. Alert fires at < 30 days.

1. For ACM-managed certs: renewal is automatic — check cert status:
   ```bash
   aws acm describe-certificate --certificate-arn <arn>
   ```
2. If status is `PENDING_VALIDATION`, re-validate DNS CNAME records.
3. For imported certs: upload a renewed cert via the console or CLI.

---

## Deployments

### Deploy to dev
Push to `main` — all service CI/CD pipelines auto-deploy to dev.

### Deploy to staging
Push a semver tag: `git tag v1.2.3 && git push origin v1.2.3`

### Deploy to prod
Trigger the relevant workflow manually in GitHub Actions UI:
- Go to **Actions → [Service] CI/CD → Run workflow**
- Select branch `main`, environment `prod`
- The `prod` GitHub environment requires approval from a designated reviewer

### Roll back prod
Re-run the last known-good workflow dispatch, or for ECS services:
```bash
# List recent task definition revisions
aws ecs list-task-definitions --family-prefix tek-watch-api --sort DESC

# Force a specific revision
aws ecs update-service --cluster tek-watch-prod \
  --service tek-watch-api \
  --task-definition tek-watch-api:<revision>
```

---

## Infrastructure changes

All infrastructure is managed via Terraform in `infrastructure/terraform/`.

```bash
# Plan dev
cd infrastructure/terraform
terraform init -backend-config="key=tek-watch/dev/terraform.tfstate"
terraform plan -var-file="environments/dev.tfvars"

# Apply (prefer doing this via GitHub Actions workflow_dispatch)
terraform apply -var-file="environments/dev.tfvars"
```

Never apply directly to prod — use the GitHub Actions `Terraform Infrastructure` workflow with `environment=prod` and `action=apply`.

---

## Required GitHub secrets

Set these in **repo Settings → Secrets and variables → Actions**, scoped to each environment:

| Secret | Scope | Description |
|---|---|---|
| `AWS_ROLE_ARN` | dev / staging / prod | OIDC role to assume for deployments |
| `ANTHROPIC_API_KEY` | dev / staging / prod | Claude API key for anomaly detection |
| `ACM_CERT_ARN_DEV` | dev | ACM cert ARN for dev domain |
| `ACM_CERT_ARN_STAGING` | staging | ACM cert ARN for staging domain |
| `ACM_CERT_ARN_PROD` | prod | ACM cert ARN for prod domain |
| `COGNITO_CUSTOMER_USER_POOL_ID_*` | per env | Customer Cognito pool IDs |
| `COGNITO_ADMIN_USER_POOL_ID_*` | per env | Admin Cognito pool IDs |
| `DASHBOARD_S3_BUCKET_*` | per env | S3 bucket for dashboard static files |
| `DASHBOARD_CF_DISTRIBUTION_*` | per env | CloudFront distribution ID for dashboard |
| `ADMIN_S3_BUCKET_*` | per env | S3 bucket for admin portal |
| `ADMIN_CF_DISTRIBUTION_*` | per env | CloudFront distribution ID for admin portal |
| `ECR_REPOSITORY_API` | repo | ECR repository URI for api image |
| `ECR_REPOSITORY_AGENT` | repo | ECR repository URI for agent image |
| `ECR_REPOSITORY_INGEST` | repo | ECR repository URI for ingest-consumer image |
| `ECS_CLUSTER_*` | per env | ECS cluster name |
| `ECS_SERVICE_API_*` | per env | ECS service name for api |

## Required GitHub environments

Create these in **repo Settings → Environments** before deploying:
- `dev` — auto-approve
- `staging` — auto-approve
- `prod` — require manual reviewer approval

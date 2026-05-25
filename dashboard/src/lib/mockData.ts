/**
 * Rich mock data for Tek Watch investor demo.
 * All pages fall back to this when the API is unavailable.
 */

// ─── Helpers ──────────────────────────────────────────────────────────────────

function hoursAgo(h: number) { return new Date(Date.now() - h * 3_600_000).toISOString() }
function minsAgo(m: number)  { return new Date(Date.now() - m * 60_000).toISOString() }
function daysAgo(d: number)  { return new Date(Date.now() - d * 86_400_000).toISOString() }

/** Seeded noise — deterministic so the page doesn't jump on re-render */
function noise(seed: number, i: number): number {
  const x = Math.sin(seed * 9301 + i * 49297 + 233995) * 0.5 + 0.5
  return x
}

/** Generate 24-hour time series at 1h intervals */
export function gen24h(base: number, variance: number, seed = 42) {
  return Array.from({ length: 24 }, (_, i) => ({
    time: hoursAgo(23 - i),
    value: Math.max(0, +(base + (noise(seed, i) - 0.5) * variance).toFixed(2)),
  }))
}

/** Generate 30-day daily cost series */
export function genDailyCosts(base: number, variance: number, seed = 77) {
  return Array.from({ length: 30 }, (_, i) => ({
    time: daysAgo(29 - i),
    cost: Math.max(0, +(base + (noise(seed, i) - 0.5) * variance).toFixed(2)),
  }))
}

// ─── Customer ─────────────────────────────────────────────────────────────────

export const MOCK_CUSTOMER = {
  customerId: 'TT-0042',
  name: 'Acme Technologies Ltd',
  tier: 'Enterprise',
  awsAccountId: '123456789012',
  regions: ['eu-west-2', 'eu-west-1', 'us-east-1'],
}

// ─── Overview ─────────────────────────────────────────────────────────────────

export const MOCK_OVERVIEW = {
  total_resources: 847,
  active_alarms: 3,
  security_findings: 2,
  estimated_monthly_cost: 4247.80,
  agent_status: { status: 'healthy', last_seen: minsAgo(2) },
  top_alarms: [
    {
      alert_id: 'ALT-001',
      severity: 'critical',
      service: 'EC2',
      description: 'CPU utilisation on web-server-01 is 92.4 % (threshold: 80 %)',
      triggered_at: minsAgo(15),
    },
    {
      alert_id: 'ALT-002',
      severity: 'warning',
      service: 'RDS',
      description: 'Connection pool on prod-db-01 is 89 % full (threshold: 85 %)',
      triggered_at: minsAgo(42),
    },
    {
      alert_id: 'ALT-003',
      severity: 'warning',
      service: 'Lambda',
      description: 'AI detected: cold-start latency spiked 340 % in the last 2 h',
      triggered_at: hoursAgo(2),
      type: 'ai_anomaly',
    },
  ],
}

// ─── Compute — EC2 ────────────────────────────────────────────────────────────

export const MOCK_EC2 = [
  { instance_id: 'i-0a1b2c3d4e5f6781', instance_name: 'web-server-01',   instance_type: 't3.large',   state: 'running', region: 'eu-west-2', az: 'eu-west-2a', cpu: 92.4, net_in: 145.2, net_out: 89.7,  public_ip: '18.134.22.45',  private_ip: '10.0.1.12' },
  { instance_id: 'i-0a1b2c3d4e5f6782', instance_name: 'web-server-02',   instance_type: 't3.large',   state: 'running', region: 'eu-west-2', az: 'eu-west-2b', cpu: 41.2, net_in: 112.4, net_out: 67.3,  public_ip: '18.134.22.46',  private_ip: '10.0.1.13' },
  { instance_id: 'i-0a1b2c3d4e5f6783', instance_name: 'api-server-01',   instance_type: 'c5.xlarge',  state: 'running', region: 'eu-west-2', az: 'eu-west-2a', cpu: 28.7, net_in:  88.1, net_out: 210.3, public_ip: '18.134.22.47',  private_ip: '10.0.2.10' },
  { instance_id: 'i-0a1b2c3d4e5f6784', instance_name: 'api-server-02',   instance_type: 'c5.xlarge',  state: 'running', region: 'eu-west-2', az: 'eu-west-2b', cpu: 32.1, net_in:  91.3, net_out: 198.7, public_ip: '18.134.22.48',  private_ip: '10.0.2.11' },
  { instance_id: 'i-0a1b2c3d4e5f6785', instance_name: 'worker-01',       instance_type: 'm5.large',   state: 'running', region: 'eu-west-2', az: 'eu-west-2c', cpu: 67.3, net_in:  34.5, net_out:  28.9, public_ip: null,             private_ip: '10.0.3.20' },
  { instance_id: 'i-0a1b2c3d4e5f6786', instance_name: 'worker-02',       instance_type: 'm5.large',   state: 'running', region: 'eu-west-2', az: 'eu-west-2c', cpu: 71.8, net_in:  39.2, net_out:  31.4, public_ip: null,             private_ip: '10.0.3.21' },
  { instance_id: 'i-0a1b2c3d4e5f6787', instance_name: 'bastion',         instance_type: 't3.micro',   state: 'running', region: 'eu-west-2', az: 'eu-west-2a', cpu:  2.1, net_in:   1.2, net_out:   0.8, public_ip: '18.134.22.49',  private_ip: '10.0.0.5'  },
  { instance_id: 'i-0a1b2c3d4e5f6788', instance_name: 'analytics-01',    instance_type: 'r5.xlarge',  state: 'running', region: 'eu-west-1', az: 'eu-west-1a', cpu: 44.6, net_in:  56.8, net_out:  74.2, public_ip: null,             private_ip: '10.1.1.10' },
  { instance_id: 'i-0a1b2c3d4e5f6789', instance_name: 'cache-01',        instance_type: 'r5.large',   state: 'running', region: 'eu-west-1', az: 'eu-west-1b', cpu: 18.3, net_in: 200.4, net_out: 315.6, public_ip: null,             private_ip: '10.1.2.10' },
  { instance_id: 'i-0a1b2c3d4e5f678a', instance_name: 'dr-web-01',       instance_type: 't3.medium',  state: 'stopped', region: 'us-east-1', az: 'us-east-1a', cpu:  0.0, net_in:   0.0, net_out:   0.0, public_ip: null,             private_ip: '10.2.1.10' },
  { instance_id: 'i-0a1b2c3d4e5f678b', instance_name: 'dr-api-01',       instance_type: 'c5.large',   state: 'stopped', region: 'us-east-1', az: 'us-east-1b', cpu:  0.0, net_in:   0.0, net_out:   0.0, public_ip: null,             private_ip: '10.2.2.10' },
  { instance_id: 'i-0a1b2c3d4e5f678c', instance_name: 'monitoring-01',   instance_type: 't3.small',   state: 'running', region: 'eu-west-2', az: 'eu-west-2a', cpu:  8.9, net_in:   4.3, net_out:   2.1, public_ip: '18.134.22.50',  private_ip: '10.0.0.10' },
]

// ─── Compute — Lambda ─────────────────────────────────────────────────────────

export const MOCK_LAMBDA = [
  { name: 'acme-api-handler',      runtime: 'python3.12', memory_mb: 512,  timeout_s: 30,  invocations_1h: 12480, errors_1h: 24,  duration_avg_ms: 142, throttles_1h: 0  },
  { name: 'acme-image-processor',  runtime: 'python3.12', memory_mb: 1024, timeout_s: 60,  invocations_1h:  3210, errors_1h:  8,  duration_avg_ms: 890, throttles_1h: 12 },
  { name: 'acme-email-sender',     runtime: 'nodejs18.x', memory_mb: 256,  timeout_s: 10,  invocations_1h:   847, errors_1h:  0,  duration_avg_ms:  67, throttles_1h: 0  },
  { name: 'acme-data-sync',        runtime: 'python3.12', memory_mb: 512,  timeout_s: 300, invocations_1h:    48, errors_1h:  2,  duration_avg_ms:4120, throttles_1h: 0  },
  { name: 'acme-auth-webhook',     runtime: 'nodejs18.x', memory_mb: 128,  timeout_s: 5,   invocations_1h:  5634, errors_1h:  0,  duration_avg_ms:  28, throttles_1h: 0  },
  { name: 'tribe-watch-silence',   runtime: 'python3.12', memory_mb: 256,  timeout_s: 30,  invocations_1h:    12, errors_1h:  0,  duration_avg_ms: 210, throttles_1h: 0  },
]

// ─── Compute — ECS ────────────────────────────────────────────────────────────

export const MOCK_ECS = [
  { cluster: 'acme-prod',    service: 'api-service',         desired: 4, running: 4, cpu_pct: 31.2, mem_pct: 48.7 },
  { cluster: 'acme-prod',    service: 'worker-service',      desired: 2, running: 2, cpu_pct: 69.4, mem_pct: 55.3 },
  { cluster: 'acme-prod',    service: 'scheduler-service',   desired: 1, running: 1, cpu_pct:  8.1, mem_pct: 22.6 },
  { cluster: 'acme-staging', service: 'api-service',         desired: 2, running: 2, cpu_pct: 14.3, mem_pct: 31.1 },
  { cluster: 'tribe-watch',  service: 'tribe-watch-api',     desired: 2, running: 2, cpu_pct: 12.4, mem_pct: 38.2 },
  { cluster: 'tribe-watch',  service: 'ingest-consumer',     desired: 1, running: 1, cpu_pct:  6.7, mem_pct: 19.8 },
]

// ─── Databases — RDS ──────────────────────────────────────────────────────────

export const MOCK_RDS = [
  { id: 'prod-db-01',     engine: 'aurora-mysql',    class: 'db.r5.large',  status: 'available', region: 'eu-west-2', cpu: 34.2, connections: 187, max_connections: 210, storage_gb: 200, iops: 1240, read_latency_ms: 1.2, write_latency_ms: 2.1, multi_az: true  },
  { id: 'prod-db-read-01',engine: 'aurora-mysql',    class: 'db.r5.large',  status: 'available', region: 'eu-west-2', cpu: 22.1, connections:  89, max_connections: 210, storage_gb: 200, iops:  890, read_latency_ms: 0.9, write_latency_ms: 0.0, multi_az: false },
  { id: 'analytics-db-01',engine: 'postgres14',      class: 'db.m5.xlarge', status: 'available', region: 'eu-west-1', cpu: 18.7, connections:  34, max_connections: 500, storage_gb: 500, iops:  340, read_latency_ms: 2.4, write_latency_ms: 3.8, multi_az: true  },
]

export const MOCK_DYNAMODB = [
  { name: 'acme-users',       status: 'ACTIVE', read_capacity: 25,  write_capacity: 25,  item_count: 148432, size_gb: 2.3, throttled_reads: 0, throttled_writes: 0  },
  { name: 'acme-sessions',    status: 'ACTIVE', read_capacity: 50,  write_capacity: 50,  item_count: 892341, size_gb: 4.1, throttled_reads: 12, throttled_writes: 3 },
  { name: 'acme-events',      status: 'ACTIVE', read_capacity: 100, write_capacity: 100, item_count:4230000, size_gb:18.7, throttled_reads: 0, throttled_writes: 0  },
  { name: 'tribe-watch-data', status: 'ACTIVE', read_capacity: 10,  write_capacity: 10,  item_count:  12430, size_gb: 0.4, throttled_reads: 0, throttled_writes: 0  },
]

// ─── Networking ───────────────────────────────────────────────────────────────

export const MOCK_VPCS = [
  { id: 'vpc-0a1b2c3d4e5f', name: 'acme-prod-vpc',    cidr: '10.0.0.0/16', region: 'eu-west-2', subnets: 6, nat_gateways: 2, state: 'available' },
  { id: 'vpc-0a1b2c3d4e60', name: 'acme-staging-vpc', cidr: '10.1.0.0/16', region: 'eu-west-1', subnets: 4, nat_gateways: 1, state: 'available' },
]

export const MOCK_ELBS = [
  { name: 'acme-prod-alb',     type: 'application', region: 'eu-west-2', scheme: 'internet-facing', requests_pm: 84320, req_5xx_pct: 0.12, latency_ms: 38,  active_targets: 8,  healthy_targets: 8  },
  { name: 'acme-internal-alb', type: 'application', region: 'eu-west-2', scheme: 'internal',        requests_pm: 31200, req_5xx_pct: 0.04, latency_ms: 12,  active_targets: 4,  healthy_targets: 4  },
  { name: 'acme-api-nlb',      type: 'network',     region: 'eu-west-2', scheme: 'internet-facing', requests_pm:210000, req_5xx_pct: 0.0,  latency_ms:  2.4, active_targets: 4, healthy_targets: 4 },
]

export const MOCK_CLOUDFRONT = [
  { id: 'E1ABCDEF12345A', domain: 'cdn.acme.com',   status: 'Deployed', origins: 2, requests_pm: 450320, error_pct: 0.08, cache_hit_pct: 94.2 },
  { id: 'E1ABCDEF12345B', domain: 'assets.acme.com',status: 'Deployed', origins: 1, requests_pm: 120450, error_pct: 0.01, cache_hit_pct: 98.7 },
]

// ─── Storage — S3 ─────────────────────────────────────────────────────────────

export const MOCK_S3 = [
  { name: 'acme-prod-assets',      region: 'eu-west-2', size_gb: 1240.5, object_count: 2340891, versioning: true,  encrypted: true  },
  { name: 'acme-user-uploads',     region: 'eu-west-2', size_gb:  890.3, object_count:  891234, versioning: true,  encrypted: true  },
  { name: 'acme-data-exports',     region: 'eu-west-2', size_gb:  430.8, object_count:   12430, versioning: false, encrypted: true  },
  { name: 'acme-backups',          region: 'eu-west-2', size_gb: 1120.4, object_count:   87432, versioning: true,  encrypted: true  },
  { name: 'acme-logs',             region: 'eu-west-2', size_gb:  340.2, object_count: 5430000, versioning: false, encrypted: true  },
  { name: 'acme-staging-assets',   region: 'eu-west-1', size_gb:   89.4, object_count:  234000, versioning: false, encrypted: true  },
  { name: 'acme-cf-logs',          region: 'us-east-1', size_gb:   67.8, object_count:  890000, versioning: false, encrypted: false },
  { name: 'tribe-watch-templates', region: 'eu-west-2', size_gb:    0.1, object_count:      42, versioning: true,  encrypted: true  },
]

// ─── Messaging ────────────────────────────────────────────────────────────────

export const MOCK_SQS = [
  { name: 'acme-jobs-queue',      messages_visible: 1247, messages_in_flight: 23,  oldest_msg_age_s: 142,  dlq: 'acme-jobs-dlq',      dlq_depth: 3  },
  { name: 'acme-email-queue',     messages_visible:    0, messages_in_flight:  0,  oldest_msg_age_s: 0,    dlq: 'acme-email-dlq',     dlq_depth: 0  },
  { name: 'acme-notifications',   messages_visible:   12, messages_in_flight:  2,  oldest_msg_age_s:  28,  dlq: 'acme-notif-dlq',     dlq_depth: 0  },
  { name: 'tribe-watch-ingest',   messages_visible:    0, messages_in_flight:  0,  oldest_msg_age_s: 0,    dlq: 'tribe-watch-dlq',    dlq_depth: 0  },
]

export const MOCK_SNS = [
  { name: 'acme-alerts',        arn: 'arn:aws:sns:eu-west-2:123456789012:acme-alerts',        subscriptions: 8,  messages_published_1h: 342 },
  { name: 'acme-user-events',   arn: 'arn:aws:sns:eu-west-2:123456789012:acme-user-events',   subscriptions: 4,  messages_published_1h: 8934 },
  { name: 'tribe-watch-ops',    arn: 'arn:aws:sns:eu-west-2:123456789012:tribe-watch-ops',    subscriptions: 3,  messages_published_1h: 12 },
]

// ─── Security ─────────────────────────────────────────────────────────────────

export const MOCK_GUARDDUTY = [
  {
    id: 'gd-001',
    title: 'Recon:EC2/PortProbeUnprotectedPort',
    severity: 'MEDIUM',
    type: 'Recon:EC2/PortProbeUnprotectedPort',
    resource: 'i-0a1b2c3d4e5f6781',
    region: 'eu-west-2',
    description: 'EC2 instance web-server-01 is being probed on port 22 from external IP 185.234.xx.xx.',
    count: 47,
    first_seen: hoursAgo(6),
    last_seen: minsAgo(18),
  },
  {
    id: 'gd-002',
    title: 'UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration',
    severity: 'HIGH',
    type: 'UnauthorizedAccess:IAMUser',
    resource: 'IAMUser/api-deploy-user',
    region: 'eu-west-2',
    description: 'API credentials for api-deploy-user were used from an IP address outside your normal operating range.',
    count: 3,
    first_seen: hoursAgo(1),
    last_seen: minsAgo(45),
  },
]

export const MOCK_IAM = {
  users_total: 24,
  users_without_mfa: 3,
  old_access_keys: 2,          // keys > 90 days
  unused_roles: 5,             // roles unused > 90 days
  root_mfa_enabled: true,
  root_access_keys: false,
}

export const MOCK_ACM_CERTS = [
  { domain: '*.acme.com',        status: 'ISSUED', expiry: daysAgo(-89),  days_remaining: 89  },
  { domain: 'api.acme.com',      status: 'ISSUED', expiry: daysAgo(-124), days_remaining: 124 },
  { domain: 'cdn.acme.com',      status: 'ISSUED', expiry: daysAgo(-211), days_remaining: 211 },
  { domain: '*.staging.acme.com',status: 'ISSUED', expiry: daysAgo(-18),  days_remaining: 18  },
]

export const MOCK_CW_ALARMS = [
  { name: 'web-server-01-HighCPU',      state: 'ALARM',      namespace: 'AWS/EC2',     metric: 'CPUUtilization'       },
  { name: 'prod-db-01-ConnectionsHigh', state: 'ALARM',      namespace: 'AWS/RDS',     metric: 'DatabaseConnections'  },
  { name: 'acme-prod-alb-5xxErrors',    state: 'OK',         namespace: 'AWS/ApplicationELB', metric: '5XXCount'      },
  { name: 'acme-jobs-queue-Depth',      state: 'INSUFFICIENT_DATA', namespace: 'AWS/SQS', metric: 'ApproximateNumberOfMessagesVisible' },
  { name: 'api-server-01-MemoryHigh',   state: 'OK',         namespace: 'AWS/EC2',     metric: 'mem_used_percent'     },
]

// ─── Cost ─────────────────────────────────────────────────────────────────────

export const MOCK_COST_SUMMARY = {
  mtd_total: 2891.40,
  last_month_total: 4247.80,
  forecasted_monthly: 4180.00,
  daily_costs: genDailyCosts(141.6, 40),
}

export const MOCK_COST_BREAKDOWN = {
  breakdown: [
    { aws_service: 'Amazon EC2',             mtd_cost: 1080.40, vs_last_month: -4.2 },
    { aws_service: 'Amazon RDS',             mtd_cost:  620.80, vs_last_month: +1.8 },
    { aws_service: 'Amazon CloudFront',      mtd_cost:  340.20, vs_last_month: +12.4 },
    { aws_service: 'Amazon S3',              mtd_cost:  220.60, vs_last_month: +6.1 },
    { aws_service: 'AWS Lambda',             mtd_cost:  180.30, vs_last_month: +38.7 },
    { aws_service: 'Amazon ECS',             mtd_cost:  160.40, vs_last_month: -2.1 },
    { aws_service: 'Amazon DynamoDB',        mtd_cost:   98.70, vs_last_month: +4.3 },
    { aws_service: 'Amazon ElastiCache',     mtd_cost:   87.40, vs_last_month: -1.0 },
    { aws_service: 'AWS Secrets Manager',    mtd_cost:   44.20, vs_last_month: +0.0 },
    { aws_service: 'Amazon SQS',             mtd_cost:   22.40, vs_last_month: +8.2 },
    { aws_service: 'Amazon SNS',             mtd_cost:   16.80, vs_last_month: +2.4 },
    { aws_service: 'Other',                  mtd_cost:   19.20, vs_last_month: -3.1 },
  ],
}

// ─── Alerts ───────────────────────────────────────────────────────────────────

export const MOCK_ALERTS = [
  {
    alert_id: 'ALT-001',
    type: 'threshold',
    severity: 'critical',
    service: 'EC2',
    resource_id: 'i-0a1b2c3d4e5f6781',
    resource_name: 'web-server-01',
    metric_name: 'CPUUtilization',
    current_value: 92.4,
    threshold_value: 80,
    description: 'CPU utilisation is 92.4% on web-server-01, exceeding the 80% critical threshold for 15+ minutes.',
    recommendation: 'Scale out the web tier — add a second t3.large instance or enable Auto Scaling. Review recent deployments for memory leaks or inefficient queries.',
    status: 'active',
    triggered_at: minsAgo(15),
    acknowledged_at: null,
  },
  {
    alert_id: 'ALT-002',
    type: 'threshold',
    severity: 'warning',
    service: 'RDS',
    resource_id: 'prod-db-01',
    resource_name: 'prod-db-01 (Aurora MySQL)',
    metric_name: 'DatabaseConnections',
    current_value: 187,
    threshold_value: 180,
    description: 'Active DB connections (187) is approaching the max_connections limit (210). Connection pool is 89% exhausted.',
    recommendation: 'Enable RDS Proxy to pool and reuse connections. Review application connection pool settings — consider adding connection pooling at the app layer.',
    status: 'active',
    triggered_at: minsAgo(42),
    acknowledged_at: null,
  },
  {
    alert_id: 'ALT-003',
    type: 'ai_anomaly',
    severity: 'warning',
    service: 'Lambda',
    resource_id: 'acme-image-processor',
    resource_name: 'acme-image-processor',
    metric_name: 'InitDuration',
    current_value: 3400,
    threshold_value: null,
    description: 'AI anomaly detected: cold-start (init) duration for acme-image-processor increased 340% over the last 2 hours (avg 3.4 s vs baseline 0.8 s).',
    recommendation: 'Investigate recent dependency changes — a new package version may have significantly increased the deployment package size. Consider enabling Lambda SnapStart or provisioned concurrency for this function.',
    status: 'active',
    triggered_at: hoursAgo(2),
    acknowledged_at: null,
  },
  {
    alert_id: 'ALT-004',
    type: 'threshold',
    severity: 'warning',
    service: 'SQS',
    resource_id: 'acme-jobs-queue',
    resource_name: 'acme-jobs-queue',
    metric_name: 'ApproximateNumberOfMessagesVisible',
    current_value: 1247,
    threshold_value: 1000,
    description: 'Queue depth on acme-jobs-queue has reached 1,247 messages (threshold: 1,000). Processing may be falling behind.',
    recommendation: 'Scale out the worker fleet or check for slow/stuck consumers. Verify the DLQ — 3 messages suggest some jobs are failing permanently.',
    status: 'acknowledged',
    triggered_at: hoursAgo(5),
    acknowledged_at: hoursAgo(4),
  },
  {
    alert_id: 'ALT-005',
    type: 'ai_anomaly',
    severity: 'info',
    service: 'Cost',
    resource_id: 'AWS/Lambda',
    resource_name: 'Lambda Cost',
    metric_name: 'DailyCost',
    current_value: 12.40,
    threshold_value: null,
    description: 'AI cost insight: Lambda spend is trending +38.7% month-over-month, driven mainly by acme-image-processor invocation growth.',
    recommendation: 'Analyse if the growth is proportional to business activity. If not, review for unnecessary retries or inefficient fan-out patterns.',
    status: 'acknowledged',
    triggered_at: hoursAgo(18),
    acknowledged_at: hoursAgo(17),
  },
]

// ─── Agent ────────────────────────────────────────────────────────────────────

export const MOCK_AGENT = {
  status: 'healthy',
  version: '1.4.2',
  customer_id: 'TT-0042',
  last_heartbeat: minsAgo(2),
  collection_interval_s: 300,
  metrics_collected_total: 1_847_320,
  regions: ['eu-west-2', 'eu-west-1', 'us-east-1'],
  collectors: [
    { name: 'EC2',            status: 'ok', last_run: minsAgo(3),  resources: 12, metrics_sent: 144 },
    { name: 'Lambda',         status: 'ok', last_run: minsAgo(3),  resources:  6, metrics_sent:  72 },
    { name: 'RDS',            status: 'ok', last_run: minsAgo(3),  resources:  3, metrics_sent:  54 },
    { name: 'DynamoDB',       status: 'ok', last_run: minsAgo(3),  resources:  4, metrics_sent:  32 },
    { name: 'ECS',            status: 'ok', last_run: minsAgo(3),  resources:  6, metrics_sent:  48 },
    { name: 'S3',             status: 'ok', last_run: minsAgo(8),  resources:  8, metrics_sent:  24 },
    { name: 'SQS',            status: 'ok', last_run: minsAgo(3),  resources:  4, metrics_sent:  32 },
    { name: 'SNS',            status: 'ok', last_run: minsAgo(3),  resources:  3, metrics_sent:  18 },
    { name: 'ELB/ALB',        status: 'ok', last_run: minsAgo(3),  resources:  3, metrics_sent:  36 },
    { name: 'CloudFront',     status: 'ok', last_run: minsAgo(8),  resources:  2, metrics_sent:  16 },
    { name: 'Route53',        status: 'ok', last_run: minsAgo(8),  resources:  2, metrics_sent:   8 },
    { name: 'GuardDuty',      status: 'ok', last_run: minsAgo(3),  resources:  2, metrics_sent:  12 },
    { name: 'ACM',            status: 'ok', last_run: minsAgo(8),  resources:  4, metrics_sent:   8 },
    { name: 'IAM',            status: 'ok', last_run: minsAgo(18), resources: 24, metrics_sent:  48 },
    { name: 'Cost Explorer',  status: 'ok', last_run: minsAgo(18), resources:  1, metrics_sent:  24 },
    { name: 'CloudWatch',     status: 'ok', last_run: minsAgo(3),  resources:  5, metrics_sent:  20 },
    { name: 'Trusted Advisor',status: 'ok', last_run: minsAgo(18), resources:  1, metrics_sent:   5 },
  ],
}

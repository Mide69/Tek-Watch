/**
 * Rich mock data for Tek Watch — fully time-range-aware.
 * Every generator accepts a TimeRange so charts update when the picker changes.
 */

import type { TimeRange } from '@/contexts/DashboardContext'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function hoursAgo(h: number)  { return new Date(Date.now() - h  * 3_600_000).toISOString() }
function minsAgo(m: number)   { return new Date(Date.now() - m  * 60_000).toISOString() }
function hoursAhead(h: number) { return new Date(Date.now() + h * 3_600_000).toISOString() }
function daysAhead(d: number)  { return new Date(Date.now() + d * 86_400_000).toISOString() }
function daysAgo(d: number)   { return new Date(Date.now() - d  * 86_400_000).toISOString() }

/** Deterministic seeded noise — no flicker on re-render */
function noise(seed: number, i: number): number {
  return Math.sin(seed * 9301 + i * 49297 + 233995) * 0.5 + 0.5
}

// Time range → { points, msPerPoint }
const RANGE_CFG: Record<TimeRange, { points: number; ms: number }> = {
  '1h':  { points: 12, ms: 5   * 60_000 },
  '6h':  { points: 12, ms: 30  * 60_000 },
  '24h': { points: 24, ms: 60  * 60_000 },
  '7d':  { points: 28, ms: 6   * 3_600_000 },
  '30d': { points: 30, ms: 24  * 3_600_000 },
}

/** Generate a time-range-aware metric series */
export function genSeries(
  timeRange: TimeRange,
  base: number,
  variance: number,
  seed = 42,
  trend = 0,               // positive = upward trend, negative = downward
) {
  const { points, ms } = RANGE_CFG[timeRange]
  return Array.from({ length: points }, (_, i) => ({
    time: new Date(Date.now() - (points - 1 - i) * ms).toISOString(),
    value: Math.max(0, +(
      base +
      trend * (i / points) * base * 0.3 +
      (noise(seed, i) - 0.5) * variance
    ).toFixed(2)),
  }))
}

/** Backward-compat alias */
export function gen24h(base: number, variance: number, seed = 42) {
  return genSeries('24h', base, variance, seed)
}

/** Generate daily cost series for the selected range */
export function genDailyCosts(timeRange: TimeRange, base: number, variance: number, seed = 77) {
  const { points, ms } = RANGE_CFG[timeRange]
  const msPerDay = 86_400_000
  return Array.from({ length: points }, (_, i) => ({
    time: new Date(Date.now() - (points - 1 - i) * ms).toISOString(),
    cost: Math.max(0, +(base + (noise(seed, i) - 0.5) * variance).toFixed(2)),
    label: timeRange === '30d' || timeRange === '7d'
      ? new Date(Date.now() - (points - 1 - i) * ms).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
      : new Date(Date.now() - (points - 1 - i) * ms).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
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

export function getMockOverview(timeRange: TimeRange = '24h') {
  const multiplier = timeRange === '1h' ? 0.85 : timeRange === '6h' ? 0.9 : timeRange === '7d' ? 1.05 : timeRange === '30d' ? 1.12 : 1
  return {
    total_resources: Math.round(847 * multiplier),
    resources_by_region: [
      { region: 'eu-west-2', count: Math.round(644 * multiplier) },
      { region: 'eu-west-1', count: Math.round(144 * multiplier) },
      { region: 'us-east-1', count: Math.round(59 * multiplier) },
    ] as RegionCount[],
    resources_by_service: [] as Array<{ service: string; count: number }>,
    active_alarms: timeRange === '1h' ? 2 : 3,
    // The API defines this as active alerts at high or critical severity
    // (api/routers/overview.py). The demo has 3 active alerts, one critical,
    // so the rule gives 1. It was hardcoded to 2, which contradicted the
    // Security page and put two different answers in the business plan.
    security_findings: 1,
    estimated_monthly_cost: +(4247.80 * multiplier).toFixed(2),
    cost_trend: genDailyCosts(timeRange, 142, 28, 77),
    agent_status: { status: 'healthy' as const, last_seen: minsAgo(2) },
    top_alarms: [] as unknown[],  // populated by useAlerts hook to avoid circular init
  }
}

// Keep static export for pages not yet converted
export const MOCK_OVERVIEW = getMockOverview('24h')

// ─── Compute — EC2 ────────────────────────────────────────────────────────────

export const MOCK_EC2 = [
  { instance_id: 'i-0a1b2c3d4e5f6781', instance_name: 'web-server-01', instance_type: 't3.large',  state: 'running', region: 'eu-west-2', az: 'eu-west-2a', cpu: 92.4, memory: 78.3, network_in: 145.2, network_out: 89.1, private_ip: '10.0.1.12', metrics: null },
  { instance_id: 'i-0a1b2c3d4e5f6782', instance_name: 'web-server-02', instance_type: 't3.large',  state: 'running', region: 'eu-west-2', az: 'eu-west-2b', cpu: 41.2, memory: 52.1, network_in: 98.7,  network_out: 45.2, private_ip: '10.0.1.13', metrics: null },
  { instance_id: 'i-0a1b2c3d4e5f6783', instance_name: 'api-server-01', instance_type: 't3.xlarge', state: 'running', region: 'eu-west-2', az: 'eu-west-2a', cpu: 28.6, memory: 41.7, network_in: 234.5, network_out: 189.3,private_ip: '10.0.2.10', metrics: null },
  { instance_id: 'i-0a1b2c3d4e5f6784', instance_name: 'api-server-02', instance_type: 't3.xlarge', state: 'running', region: 'eu-west-2', az: 'eu-west-2c', cpu: 32.1, memory: 38.4, network_in: 198.2, network_out: 156.7,private_ip: '10.0.2.11', metrics: null },
  { instance_id: 'i-0a1b2c3d4e5f6785', instance_name: 'worker-01',    instance_type: 'c5.large',  state: 'running', region: 'eu-west-2', az: 'eu-west-2a', cpu: 67.3, memory: 61.2, network_in: 12.4,  network_out: 8.9,  private_ip: '10.0.3.20', metrics: null },
  { instance_id: 'i-0a1b2c3d4e5f6786', instance_name: 'worker-02',    instance_type: 'c5.large',  state: 'running', region: 'eu-west-2', az: 'eu-west-2b', cpu: 71.8, memory: 58.9, network_in: 15.3,  network_out: 11.2, private_ip: '10.0.3.21', metrics: null },
  { instance_id: 'i-0a1b2c3d4e5f6787', instance_name: 'analytics-01', instance_type: 'r5.large',  state: 'running', region: 'eu-west-1', az: 'eu-west-1a', cpu: 44.6, memory: 82.1, network_in: 67.8,  network_out: 34.5, private_ip: '10.1.1.10', metrics: null },
  { instance_id: 'i-0a1b2c3d4e5f6788', instance_name: 'bastion-01',   instance_type: 't3.micro',  state: 'running', region: 'eu-west-2', az: 'eu-west-2a', cpu: 1.2,  memory: 12.3, network_in: 0.4,   network_out: 0.2,  private_ip: '10.0.0.5',  metrics: null },
  { instance_id: 'i-0a1b2c3d4e5f6789', instance_name: 'staging-web',  instance_type: 't3.medium', state: 'stopped', region: 'eu-west-2', az: 'eu-west-2a', cpu: 0,    memory: 0,    network_in: 0,     network_out: 0,    private_ip: '10.0.4.10', metrics: null },
  { instance_id: 'i-0a1b2c3d4e5f678a', instance_name: 'ml-training',  instance_type: 'p3.2xlarge',state: 'stopped', region: 'us-east-1', az: 'us-east-1a', cpu: 0,    memory: 0,    network_in: 0,     network_out: 0,    private_ip: '10.2.1.50', metrics: null },
  { instance_id: 'i-0a1b2c3d4e5f678b', instance_name: 'nat-instance',  instance_type: 't3.small',  state: 'running', region: 'eu-west-2', az: 'eu-west-2a', cpu: 8.4,  memory: 22.1, network_in: 432.1, network_out: 421.8,private_ip: '10.0.0.10', metrics: null },
  { instance_id: 'i-0a1b2c3d4e5f678c', instance_name: 'monitoring-01',instance_type: 't3.medium', state: 'running', region: 'eu-west-2', az: 'eu-west-2b', cpu: 18.7, memory: 44.2, network_in: 23.4,  network_out: 19.8, private_ip: '10.0.5.10', metrics: null },
]

export function getMockEC2WithMetrics(timeRange: TimeRange) {
  return MOCK_EC2.map((inst, idx) => ({
    ...inst,
    metrics: {
      cpu:    genSeries(timeRange, inst.cpu,    15, 10 + idx, inst.cpu > 70 ? 0.1 : -0.05),
      memory: genSeries(timeRange, inst.memory, 10, 20 + idx),
      net_in: genSeries(timeRange, inst.network_in, 30, 30 + idx),
    },
  }))
}

// ─── Compute — Lambda ─────────────────────────────────────────────────────────

export interface LambdaFunction {
  function_name: string
  runtime: string
  memory: number | null
  timeout: number | null
  region: string
  invocations: number | null
  errors: number | null
  duration_avg: number | null
  duration_p99: number | null
  throttles: number | null
  cold_starts: number | null
  cost_mtd: number | null
}

export const MOCK_LAMBDA: LambdaFunction[] = [
  { function_name: 'acme-image-processor',  runtime: 'python3.11', memory: 1024, timeout: 300, region: 'eu-west-2', invocations: 45230, errors: 234,  duration_avg: 3400, duration_p99: 8200, throttles: 12, cold_starts: 892, cost_mtd: 180.30 },
  { function_name: 'acme-api-authorizer',   runtime: 'nodejs18.x', memory: 256,  timeout: 10,  region: 'eu-west-2', invocations: 892441,errors: 12,   duration_avg: 42,   duration_p99: 180,  throttles: 0,  cold_starts: 1240,cost_mtd: 42.10  },
  { function_name: 'acme-data-sync',        runtime: 'python3.11', memory: 512,  timeout: 900, region: 'eu-west-2', invocations: 1440,  errors: 0,    duration_avg: 28000,duration_p99: 45000,throttles: 0,  cold_starts: 48,  cost_mtd: 28.50  },
  { function_name: 'acme-email-sender',     runtime: 'nodejs18.x', memory: 256,  timeout: 60,  region: 'eu-west-1', invocations: 8920,  errors: 18,   duration_avg: 340,  duration_p99: 890,  throttles: 0,  cold_starts: 210, cost_mtd: 8.20   },
  { function_name: 'acme-report-generator', runtime: 'python3.11', memory: 2048, timeout: 900, region: 'eu-west-2', invocations: 288,   errors: 2,    duration_avg: 125000,duration_p99: 240000,throttles: 0,cold_starts: 24,  cost_mtd: 62.40  },
  { function_name: 'acme-webhook-handler',  runtime: 'nodejs18.x', memory: 512,  timeout: 30,  region: 'eu-west-2', invocations: 234100,errors: 89,   duration_avg: 180,  duration_p99: 420,  throttles: 4,  cold_starts: 456, cost_mtd: 48.90  },
]

export function getMockLambdaWithMetrics(timeRange: TimeRange) {
  return MOCK_LAMBDA.map((fn, idx) => ({
    ...fn,
    metrics: {
      invocations: genSeries(timeRange, (fn.invocations ?? 0) / 24, 200, 50 + idx, fn.function_name === 'acme-image-processor' ? 0.4 : 0),
      errors:      genSeries(timeRange, (fn.errors ?? 0) / 24,       5,  60 + idx),
      duration:    genSeries(timeRange, fn.duration_avg ?? 0,      500,  70 + idx, fn.function_name === 'acme-image-processor' ? 0.5 : 0),
    },
  }))
}

// ─── Compute — ECS ────────────────────────────────────────────────────────────

export interface ECSService {
  service_name: string
  cluster: string
  desired: number | null
  running: number | null
  pending: number | null
  cpu: number | null
  memory: number | null
  region: string
  status: string
}

export const MOCK_ECS: ECSService[] = [
  { service_name: 'acme-web-service',     cluster: 'prod-cluster', desired: 4, running: 4, pending: 0, cpu: 68.2, memory: 71.4, region: 'eu-west-2', status: 'ACTIVE' },
  { service_name: 'acme-api-service',     cluster: 'prod-cluster', desired: 6, running: 6, pending: 0, cpu: 42.1, memory: 55.3, region: 'eu-west-2', status: 'ACTIVE' },
  { service_name: 'acme-worker-service',  cluster: 'prod-cluster', desired: 3, running: 3, pending: 0, cpu: 81.3, memory: 64.2, region: 'eu-west-2', status: 'ACTIVE' },
  { service_name: 'acme-ml-service',      cluster: 'ml-cluster',   desired: 2, running: 2, pending: 0, cpu: 92.7, memory: 88.1, region: 'eu-west-2', status: 'ACTIVE' },
  { service_name: 'acme-analytics',       cluster: 'analytics',    desired: 2, running: 2, pending: 0, cpu: 34.8, memory: 78.9, region: 'eu-west-1', status: 'ACTIVE' },
  { service_name: 'acme-batch-processor', cluster: 'batch-cluster', desired: 4, running: 2, pending: 2, cpu: 55.2, memory: 49.1, region: 'eu-west-2', status: 'ACTIVE' },
]

// ─── Databases — RDS ──────────────────────────────────────────────────────────

export interface RDSInstance {
  db_identifier: string
  engine: string
  instance_class: string
  status: string
  region: string
  cpu: number | null
  connections: number | null
  free_storage_gb: number | null
  read_iops: number | null
  write_iops: number | null
  replica_lag_ms: number | null
  multi_az: boolean | null
  cost_mtd: number | null
}

export const MOCK_RDS: RDSInstance[] = [
  { db_identifier: 'prod-db-01',     engine: 'aurora-mysql',    instance_class: 'db.r6g.large',  status: 'available', region: 'eu-west-2', cpu: 34.2, connections: 187, free_storage_gb: 420.5, read_iops: 1240, write_iops: 890, replica_lag_ms: 0,    multi_az: true,  cost_mtd: 620.80 },
  { db_identifier: 'analytics-db-01',engine: 'aurora-postgres', instance_class: 'db.r6g.xlarge', status: 'available', region: 'eu-west-2', cpu: 22.1, connections: 42,  free_storage_gb: 1840.2,read_iops: 340,  write_iops: 120, replica_lag_ms: 0,    multi_az: true,  cost_mtd: 840.20 },
  { db_identifier: 'staging-db-01',  engine: 'mysql',           instance_class: 'db.t3.medium',  status: 'available', region: 'eu-west-2', cpu: 8.4,  connections: 12,  free_storage_gb: 84.1,  read_iops: 45,   write_iops: 22,  replica_lag_ms: 0,    multi_az: false, cost_mtd: 48.60  },
]

export function getMockRDSWithMetrics(timeRange: TimeRange) {
  return MOCK_RDS.map((db, idx) => ({
    ...db,
    metrics: {
      cpu:         genSeries(timeRange, db.cpu ?? 0,         10, 80 + idx),
      connections: genSeries(timeRange, db.connections ?? 0, 20, 90 + idx, db.db_identifier === 'prod-db-01' ? 0.15 : 0),
      read_iops:   genSeries(timeRange, db.read_iops ?? 0,  300, 100 + idx),
    },
  }))
}

// ─── Databases — DynamoDB ─────────────────────────────────────────────────────

export interface DynamoDBTable {
  table_name: string
  status: string
  size_bytes: number | null
  item_count: number | null
  read_capacity: number | null
  write_capacity: number | null
  consumed_read: number | null
  consumed_write: number | null
  throttled_reads: number | null
  throttled_writes: number | null
  region: string
}

export const MOCK_DYNAMODB: DynamoDBTable[] = [
  { table_name: 'acme-users',        status: 'ACTIVE', size_bytes: 2_840_000_000, item_count: 284000, read_capacity: 25, write_capacity: 25, consumed_read: 12.4, consumed_write: 8.2,  throttled_reads: 0,   throttled_writes: 0,   region: 'eu-west-2' },
  { table_name: 'acme-sessions',     status: 'ACTIVE', size_bytes: 456_000_000,   item_count: 45600,  read_capacity: 50, write_capacity: 50, consumed_read: 28.7, consumed_write: 22.1, throttled_reads: 0,   throttled_writes: 0,   region: 'eu-west-2' },
  { table_name: 'acme-events',       status: 'ACTIVE', size_bytes: 18_200_000_000,item_count: 1820000,read_capacity: 100,write_capacity: 100,consumed_read: 78.2, consumed_write: 89.4, throttled_reads: 12,  throttled_writes: 8,   region: 'eu-west-2' },
  { table_name: 'acme-config',       status: 'ACTIVE', size_bytes: 12_400_000,    item_count: 1240,   read_capacity: 5,  write_capacity: 5,  consumed_read: 0.8,  consumed_write: 0.2,  throttled_reads: 0,   throttled_writes: 0,   region: 'eu-west-2' },
]

// ─── Networking ───────────────────────────────────────────────────────────────

export interface VPCResource {
  vpc_id: string
  name: string
  cidr: string
  region: string
  subnets: number | null
  route_tables: number | null
  security_groups: number | null
  nacls: number | null
  state: string
}

export const MOCK_VPCS: VPCResource[] = [
  { vpc_id: 'vpc-0a1b2c3d4e', name: 'prod-vpc',     cidr: '10.0.0.0/16',  region: 'eu-west-2', subnets: 9,  route_tables: 6,  security_groups: 24, nacls: 3, state: 'available' },
  { vpc_id: 'vpc-1b2c3d4e5f', name: 'staging-vpc',  cidr: '10.1.0.0/16',  region: 'eu-west-2', subnets: 3,  route_tables: 2,  security_groups: 8,  nacls: 1, state: 'available' },
  { vpc_id: 'vpc-2c3d4e5f6g', name: 'analytics-vpc', cidr: '10.2.0.0/16', region: 'eu-west-1', subnets: 3,  route_tables: 2,  security_groups: 6,  nacls: 1, state: 'available' },
]

export interface LoadBalancer {
  name: string
  type: string
  scheme: string
  state: string
  region: string
  dns: string
  targets: number | null
  healthy: number | null
  request_count: number | null
  latency_ms: number | null
  error_4xx: number | null
  error_5xx: number | null
}

export const MOCK_ELBS: LoadBalancer[] = [
  { name: 'prod-alb-web',    type: 'application', scheme: 'internet-facing', state: 'active', region: 'eu-west-2', dns: 'prod-alb-web-123456.eu-west-2.elb.amazonaws.com', targets: 4, healthy: 4, request_count: 284200, latency_ms: 42,  error_4xx: 0.3,  error_5xx: 0.02 },
  { name: 'prod-alb-api',    type: 'application', scheme: 'internet-facing', state: 'active', region: 'eu-west-2', dns: 'prod-alb-api-789012.eu-west-2.elb.amazonaws.com',  targets: 6, healthy: 6, request_count: 892400, latency_ms: 18,  error_4xx: 0.8,  error_5xx: 0.01 },
  { name: 'internal-nlb',    type: 'network',     scheme: 'internal',        state: 'active', region: 'eu-west-2', dns: 'internal-nlb-345678.eu-west-2.elb.amazonaws.com', targets: 3, healthy: 3, request_count: 124000, latency_ms: 4,   error_4xx: 0,    error_5xx: 0    },
  { name: 'staging-alb',     type: 'application', scheme: 'internet-facing', state: 'active', region: 'eu-west-2', dns: 'staging-alb-901234.eu-west-2.elb.amazonaws.com',  targets: 2, healthy: 2, request_count: 12400,  latency_ms: 38,  error_4xx: 1.2,  error_5xx: 0.1  },
]

export interface CloudFrontDistribution {
  id: string
  domain: string
  origins: number | null
  status: string
  enabled: boolean | null
  price_class: string
  requests_day: number | null
  bytes_day: number | null
  error_rate: number | null
  cache_hit: number | null
  region: string
}

export const MOCK_CLOUDFRONT: CloudFrontDistribution[] = [
  { id: 'E1A2B3C4D5E6F7', domain: 'd1a2b3c4d5e6f7.cloudfront.net', origins: 2, status: 'Deployed', enabled: true, price_class: 'PriceClass_100', requests_day: 4284000, bytes_day: 284_200_000_000, error_rate: 0.02, cache_hit: 89.4, region: 'global' },
  { id: 'E2B3C4D5E6F7G8', domain: 'd2b3c4d5e6f7g8.cloudfront.net', origins: 1, status: 'Deployed', enabled: true, price_class: 'PriceClass_100', requests_day: 892000,  bytes_day: 48_400_000_000,  error_rate: 0.08, cache_hit: 76.2, region: 'global' },
]

// ─── Storage — S3 ─────────────────────────────────────────────────────────────

/**
 * Shapes the live API can return, which the fixtures below must satisfy.
 *
 * A field the agent could not collect comes back null, not zero — so these are
 * declared nullable and the fixtures, which have a value for everything, still
 * typecheck against them. Without the annotation the shape is inferred from
 * the demo data, where nothing is ever missing, and every page is written
 * against a world that cannot happen on a real account.
 */
export interface S3Bucket {
  bucket_name: string
  region: string
  size_bytes: number | null
  object_count: number | null
  versioning: boolean | null
  public_access_blocked: boolean | null
  encryption: string | null
  cost_mtd: number | null
  last_seen?: string | null
}

export interface RegionCount {
  region: string
  count: number
}

export const MOCK_S3: S3Bucket[] = [
  { bucket_name: 'acme-prod-assets',        region: 'eu-west-2', size_bytes: 284_200_000_000, object_count: 2842000, versioning: true,  public_access_blocked: true,  encryption: 'SSE-S3',  cost_mtd: 48.20  },
  { bucket_name: 'acme-prod-backups',       region: 'eu-west-2', size_bytes: 1_840_000_000_000,object_count: 18400,  versioning: true,  public_access_blocked: true,  encryption: 'SSE-KMS', cost_mtd: 220.60 },
  { bucket_name: 'acme-logs',              region: 'eu-west-2', size_bytes: 89_400_000_000,  object_count: 8940000, versioning: false, public_access_blocked: true,  encryption: 'SSE-S3',  cost_mtd: 28.40  },
  { bucket_name: 'acme-ml-datasets',       region: 'eu-west-2', size_bytes: 4_280_000_000_000,object_count: 42800,  versioning: false, public_access_blocked: true,  encryption: 'SSE-KMS', cost_mtd: 84.30  },
  { bucket_name: 'acme-static-website',    region: 'eu-west-2', size_bytes: 2_400_000_000,   object_count: 24000,  versioning: true,  public_access_blocked: false, encryption: 'SSE-S3',  cost_mtd: 4.80   },
  { bucket_name: 'acme-staging-assets',    region: 'eu-west-2', size_bytes: 12_400_000_000,  object_count: 124000, versioning: false, public_access_blocked: true,  encryption: 'SSE-S3',  cost_mtd: 8.20   },
  { bucket_name: 'acme-terraform-state',   region: 'eu-west-2', size_bytes: 24_000_000,      object_count: 240,    versioning: true,  public_access_blocked: true,  encryption: 'SSE-KMS', cost_mtd: 0.80   },
  { bucket_name: 'acme-cloudtrail-logs',   region: 'eu-west-2', size_bytes: 48_200_000_000,  object_count: 482000, versioning: false, public_access_blocked: true,  encryption: 'SSE-S3',  cost_mtd: 12.40  },
]

// ─── Messaging ────────────────────────────────────────────────────────────────

export const MOCK_SQS = [
  { queue_name: 'acme-job-queue',          type: 'Standard', region: 'eu-west-2', messages_visible: 842,  messages_inflight: 24,   oldest_message_age: 42,   dlq: 'acme-job-queue-dlq',       dlq_count: 3,  throughput: 2840 },
  { queue_name: 'acme-priority-queue',     type: 'FIFO',     region: 'eu-west-2', messages_visible: 124,  messages_inflight: 8,    oldest_message_age: 12,   dlq: 'acme-priority-queue-dlq',  dlq_count: 0,  throughput: 890  },
  { queue_name: 'acme-email-queue',        type: 'Standard', region: 'eu-west-2', messages_visible: 28,   messages_inflight: 4,    oldest_message_age: 8,    dlq: 'acme-email-queue-dlq',     dlq_count: 0,  throughput: 240  },
  { queue_name: 'acme-analytics-events',   type: 'Standard', region: 'eu-west-2', messages_visible: 48200,messages_inflight: 1240,  oldest_message_age: 180,  dlq: 'acme-analytics-dlq',       dlq_count: 12, throughput: 48200 },
  { queue_name: 'acme-notifications',      type: 'Standard', region: 'eu-west-1', messages_visible: 4,    messages_inflight: 1,    oldest_message_age: 4,    dlq: null,                       dlq_count: 0,  throughput: 120  },
]

export interface SNSTopic {
  topic_name: string
  region: string
  subscriptions: number | null
  messages_day: number | null
  delivery_success: number | null
}

export const MOCK_SNS: SNSTopic[] = [
  { topic_name: 'acme-alerts',             region: 'eu-west-2', subscriptions: 8,  messages_day: 2840,  delivery_success: 99.8 },
  { topic_name: 'acme-user-events',        region: 'eu-west-2', subscriptions: 12, messages_day: 89200, delivery_success: 99.9 },
  { topic_name: 'acme-billing-events',     region: 'eu-west-2', subscriptions: 4,  messages_day: 240,   delivery_success: 100  },
  { topic_name: 'acme-infrastructure',     region: 'eu-west-2', subscriptions: 6,  messages_day: 1240,  delivery_success: 99.7 },
]

// ─── Security ─────────────────────────────────────────────────────────────────

export const MOCK_GUARDDUTY = [
  { finding_id: 'GD-001', type: 'Recon:EC2/PortProbeUnprotectedPort', severity: 'MEDIUM', region: 'eu-west-2', resource: 'web-server-01', description: 'EC2 instance web-server-01 is being probed on port 22 from external IP 185.234.xx.xx.', updated_at: hoursAgo(4),  count: 48 },
  { finding_id: 'GD-002', type: 'UnauthorizedAccess:IAMUser/MaliciousIPCaller', severity: 'HIGH', region: 'eu-west-2', resource: 'IAM user: deploy-bot', description: 'API calls were made from a known malicious IP address 91.108.xx.xx.', updated_at: hoursAgo(2), count: 3  },
]

export const MOCK_IAM = {
  users_total: 42,
  users_with_mfa: 39,
  users_without_mfa: 3,
  old_access_keys: 2,
  root_access_keys: 0,
  root_mfa_enabled: true,
  overprivileged_roles: 4,
  unused_credentials_90d: 5,
  policies_inline: 8,
  policies_customer_managed: 24,
  last_root_activity: daysAgo(47),
}

export const MOCK_ACM_CERTS = [
  { domain: '*.acme-tech.co.uk',     status: 'ISSUED', type: 'AMAZON_ISSUED', region: 'eu-west-2', expires_at: new Date(Date.now() + 84 * 86_400_000).toISOString(),  days_to_expiry: 84,  in_use: true,  auto_renew: true  },
  { domain: 'api.acme-tech.co.uk',   status: 'ISSUED', type: 'AMAZON_ISSUED', region: 'eu-west-2', expires_at: new Date(Date.now() + 22 * 86_400_000).toISOString(),  days_to_expiry: 22,  in_use: true,  auto_renew: true  },
  { domain: 'staging.acme-tech.co.uk',status:'ISSUED', type: 'AMAZON_ISSUED', region: 'eu-west-2', expires_at: new Date(Date.now() + 182 * 86_400_000).toISOString(), days_to_expiry: 182, in_use: true,  auto_renew: true  },
  { domain: 'legacy.acme-tech.co.uk', status:'ISSUED', type: 'IMPORTED',      region: 'eu-west-2', expires_at: new Date(Date.now() + 14 * 86_400_000).toISOString(),  days_to_expiry: 14,  in_use: false, auto_renew: false },
]

export const MOCK_CW_ALARMS = [
  { alarm_name: 'web-server-01-cpu-critical', state: 'ALARM',             metric: 'CPUUtilization',        threshold: 80,  value: 92.4, region: 'eu-west-2', namespace: 'AWS/EC2' },
  { alarm_name: 'prod-db-01-connections',     state: 'ALARM',             metric: 'DatabaseConnections',   threshold: 180, value: 187,  region: 'eu-west-2', namespace: 'AWS/RDS' },
  { alarm_name: 'acme-job-queue-depth',       state: 'OK',                metric: 'ApproximateNumberOfMessagesVisible', threshold: 1000, value: 842, region: 'eu-west-2', namespace: 'AWS/SQS' },
  { alarm_name: 'prod-alb-5xx-rate',          state: 'OK',                metric: 'HTTPCode_ELB_5XX_Count',threshold: 10,  value: 2,    region: 'eu-west-2', namespace: 'AWS/ApplicationELB' },
  { alarm_name: 'lambda-error-rate',          state: 'INSUFFICIENT_DATA', metric: 'Errors',                threshold: 100, value: 0,    region: 'eu-west-2', namespace: 'AWS/Lambda' },
]

// ─── Compliance checks and incidents ──────────────────────────────────────────
//
// Shapes match GET /api/v1/security/compliance and /incidents. The demo's
// results are consistent with the demo's own fixtures above: three users
// without MFA, two old keys, two certificates inside 30 days, one HIGH
// GuardDuty finding against deploy-bot. The scores are computed from the
// checks, the same way the API computes them, never typed in.

export type ControlStatus = 'pass' | 'fail' | 'unknown' | 'not_applicable'

export interface ComplianceControl {
  id: string
  title: string
  severity: string
  status: ControlStatus
  detail: string
  remediation: string
  references: { framework: string; reference: string }[]
  findings: { resource: string; detail: string }[]
}

export interface ComplianceFramework {
  id: string
  name: string
  score: number | null
  passed: number
  failed: number
  unknown: number
  total: number
  // Present on FCA PS21/3 only: a score against the technical half of a regime
  // must never be read as a score against the regime.
  scope?: string
  scope_note?: string
}

export interface ServiceImpactNode {
  key: string
  service: string
  resource_id: string
  name: string
  region: string
  relationship: string
  confidence: 'direct' | 'inferred'
  why: string
}

export interface ServiceImpact {
  serves: ServiceImpactNode[]
  reachable_from: ServiceImpactNode[]
  runs_in: ServiceImpactNode[]
  total: number
  summary: string
}

export interface CalendarEntry {
  id: string
  kind: 'deadline' | 'expiry' | 'renewal'
  title: string
  due_at: string | null
  days_remaining: number | null
  overdue: boolean
  urgency: 'overdue' | 'critical' | 'soon' | 'scheduled' | 'unknown'
  detail: string
  framework: string
  source: string | null
  action: string | null
}

export interface RegulatoryCalendar {
  generated_at: string
  entries: CalendarEntry[]
  overdue: number
  due_within_14_days: number
  awaiting_your_date: number
}

export interface ExposureReference {
  id: string
  kind: 'statutory_maximum' | 'enforcement_case' | 'direct_cost'
  applies_to?: 'all' | 'fca_regulated'
  label: string
  summary: string
  source: string
  published: string
  amount_low: number | null
  amount_high: number | null
}

export interface ExposureBand {
  low: number | null
  high: number | null
  display: string | null
  references: ExposureReference[]
}

export interface Exposure {
  failing_controls: number
  controls_with_published_exposure: number
  direct_cost: ExposureBand
  comparable_enforcement: ExposureBand
  statutory_maximum: { display: string | null; references: ExposureReference[] }
  items: {
    control_id: string
    control_title: string
    severity: string
    why: string
    references: ExposureReference[]
  }[]
  basis: string
}

export interface EvidenceEntry {
  seq: number
  recorded_at: string
  kind: 'snapshot' | 'resolved' | 'regressed' | 'anchor'
  summary: string
  hash: string
  prev_hash: string
}

export interface EvidenceLog {
  entries: EvidenceEntry[]
  total_recorded: number
  statement: string
  anchors?: number
  verification?: {
    intact: boolean
    entries_checked: number
    broken_at: number | null
    anchors?: number
    last_anchored_at?: string | null
  }
}

export interface ComplianceReport {
  evaluated_at: string
  frameworks: ComplianceFramework[]
  controls: ComplianceControl[]
  exposure?: Exposure
  disclaimer: string
}

export interface Incident {
  id: string
  type: string
  title: string
  severity: string
  correlated: boolean
  summary: string
  detected_at: string | null
  affected: { service: string; resource: string; region: string }[]
  chain: { service: string; time: string | null; detail: string }[]
  regulatory_impact: { framework: string; reference: string; why: string }[]
  operational_impact: { headline: string; points: string[] }
  service_impact?: ServiceImpact
  remediation: { order: number; action: string; command: string | null }[]
}

export const COMPLIANCE_FRAMEWORK_NAMES: Record<string, string> = {
  uk_gdpr: 'UK GDPR',
  cyber_essentials: 'Cyber Essentials v3.3',
  iso27001: 'ISO 27001:2022',
  fca_ps21_3: 'FCA PS21/3 operational resilience',
}

const PS21_3_SCOPE_NOTE =
  'Technical evidence only. These checks show whether the AWS resources behind a service can ' +
  'survive a failure and be restored, which supports the resource mapping a firm must do under ' +
  'PS21/3. Identifying important business services, setting impact tolerances and scenario ' +
  'testing are governance work that cannot be read from AWS configuration, and are not assessed here.'

const ref = (framework: string, reference: string) => ({ framework, reference })
const ACCESS_REFS = [
  ref('uk_gdpr', 'Art. 32(1)(b) confidentiality of processing systems'),
  ref('cyber_essentials', 'User access control'),
  ref('iso27001', 'A.8.5 Secure authentication'),
]

const DEMO_CONTROLS: ComplianceControl[] = [
  { id: 'S3-01', title: 'S3 buckets block public access', severity: 'high', status: 'fail',
    detail: '1 of 6 buckets fail this check.',
    remediation: 'Turn on all four S3 Block Public Access settings for each bucket, or for the whole account.',
    references: [ref('uk_gdpr', 'Art. 32(1)(b) confidentiality of processing systems'), ref('cyber_essentials', 'Secure configuration'), ref('iso27001', 'A.8.3 Information access restriction')],
    findings: [{ resource: 'acme-marketing-assets', detail: 'S3 Block Public Access is not fully enabled on this bucket.' }] },
  { id: 'IAM-01', title: 'Every IAM user with a password uses MFA', severity: 'high', status: 'fail',
    detail: '3 IAM users can sign in without MFA.',
    remediation: 'Assign an MFA device to each IAM user that can sign in to the console, and add an IAM policy that denies access without MFA.',
    references: ACCESS_REFS, findings: [{ resource: 'IAM users', detail: '3 without MFA' }] },
  { id: 'GD-02', title: 'No open high or critical GuardDuty findings', severity: 'high', status: 'fail',
    detail: '1 high or critical finding open.',
    remediation: 'Investigate each high or critical finding, contain the affected resource, and archive the finding once it is resolved.',
    references: [ref('uk_gdpr', 'Art. 33 assessing and notifying personal data breaches'), ref('iso27001', 'A.5.26 Response to information security incidents')],
    findings: [{ resource: 'GuardDuty', detail: '1 high/critical finding' }] },
  { id: 'RES-01', title: 'Databases run in more than one availability zone', severity: 'high', status: 'pass',
    detail: 'All 2 databases span two zones.',
    remediation: 'Turn on Multi-AZ for production databases.',
    references: [ref('fca_ps21_3', 'Remaining within impact tolerance when a data centre is lost'), ref('iso27001', 'A.8.14 Redundancy of information processing facilities')],
    findings: [] },
  { id: 'RES-02', title: 'Databases keep automated backups', severity: 'critical', status: 'fail',
    detail: '1 of 2 databases keep no automated backups.',
    remediation: 'Set a retention period of at least 7 days: aws rds modify-db-instance --db-instance-identifier <id> --backup-retention-period 7 --apply-immediately',
    references: [ref('fca_ps21_3', 'Ability to restore an important business service after an incident'), ref('uk_gdpr', 'Art. 32(1)(c) ability to restore availability and access'), ref('iso27001', 'A.8.13 Information backup')],
    findings: [{ resource: 'acme-reporting-db', detail: 'Backup retention is 0 days' }] },
  { id: 'IAM-03', title: 'No access keys older than 90 days', severity: 'medium', status: 'fail',
    detail: '2 access keys are older than 90 days.',
    remediation: 'Rotate each old key: create a new key, update whatever uses it, then deactivate and delete the old one.',
    references: [ref('cyber_essentials', 'User access control'), ref('iso27001', 'A.5.17 Authentication information')],
    findings: [{ resource: 'IAM access keys', detail: '2 older than 90 days' }] },
  { id: 'ACM-01', title: 'TLS certificates in use are not about to expire', severity: 'medium', status: 'fail',
    detail: '2 of 4 certificates expire within 30 days.',
    remediation: 'Renew or replace certificates before they expire.',
    references: [ref('uk_gdpr', 'Art. 32(1)(a) encryption of personal data in transit'), ref('iso27001', 'A.8.24 Use of cryptography')],
    findings: [{ resource: 'api.acme-tech.co.uk', detail: 'Expires in 22 days' }, { resource: 'legacy.acme-tech.co.uk', detail: 'Expires in 14 days' }] },
  { id: 'IAM-02', title: 'The root account uses MFA', severity: 'critical', status: 'pass',
    detail: 'The root account has MFA.', remediation: '', references: ACCESS_REFS, findings: [] },
  { id: 'S3-02', title: 'S3 buckets encrypt data at rest', severity: 'medium', status: 'pass',
    detail: 'All 6 buckets pass.', remediation: '',
    references: [ref('uk_gdpr', 'Art. 32(1)(a) encryption of personal data'), ref('iso27001', 'A.8.24 Use of cryptography')], findings: [] },
  { id: 'S3-03', title: 'S3 buckets keep previous versions', severity: 'low', status: 'pass',
    detail: 'All 6 buckets pass.', remediation: '',
    references: [ref('uk_gdpr', 'Art. 32(1)(c) ability to restore availability and access'), ref('iso27001', 'A.8.13 Information backup')], findings: [] },
  { id: 'GD-01', title: 'GuardDuty threat detection is switched on', severity: 'high', status: 'pass',
    detail: 'Enabled in eu-west-2.', remediation: '',
    references: [ref('uk_gdpr', 'Art. 32(1)(d) testing and assessing security measures'), ref('iso27001', 'A.8.16 Monitoring activities')], findings: [] },
  { id: 'CT-01', title: 'A CloudTrail trail is recording activity', severity: 'medium', status: 'pass',
    detail: 'At least one trail is logging.', remediation: '',
    references: [ref('uk_gdpr', 'Art. 5(2) accountability'), ref('iso27001', 'A.8.15 Logging')], findings: [] },

  // The rest of the 24-control library. Titles, severities and clause
  // references are those in api/services/compliance.py.
  { id: 'RDS-01', title: 'Databases are not reachable from the internet', severity: 'critical', status: 'pass',
    detail: 'Neither database has a public endpoint.', remediation: '',
    references: [ref('uk_gdpr', 'Art. 32(1)(b) confidentiality of processing systems'), ref('cyber_essentials', 'Firewalls and internet gateways'), ref('iso27001', 'A.8.20 Network security')],
    findings: [] },
  { id: 'DDB-01', title: 'DynamoDB tables can be restored to a point in time', severity: 'high', status: 'fail',
    detail: '2 of 5 tables have point-in-time recovery switched off.',
    remediation: 'Switch it on: aws dynamodb update-continuous-backups --table-name <name> --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true',
    references: [ref('uk_gdpr', 'Art. 32(1)(c) ability to restore availability and access'), ref('iso27001', 'A.8.13 Information backup'), ref('fca_ps21_3', 'Ability to recover data supporting an important business service')],
    findings: [{ resource: 'acme-sessions', detail: 'Point-in-time recovery is off' }, { resource: 'acme-audit-log', detail: 'Point-in-time recovery is off' }] },
  { id: 'SQS-01', title: 'Queues encrypt the messages they hold', severity: 'medium', status: 'pass',
    detail: 'All 4 queues encrypt messages at rest.', remediation: '',
    references: [ref('uk_gdpr', 'Art. 32(1)(a) encryption of personal data'), ref('iso27001', 'A.8.24 Use of cryptography')],
    findings: [] },
  { id: 'SNS-01', title: 'Topics encrypt the messages they carry', severity: 'medium', status: 'fail',
    detail: '1 of 3 topics carries messages unencrypted.',
    remediation: 'Attach a KMS key: aws sns set-topic-attributes --topic-arn <arn> --attribute-name KmsMasterKeyId --attribute-value alias/aws/sns',
    references: [ref('uk_gdpr', 'Art. 32(1)(a) encryption of personal data'), ref('iso27001', 'A.8.24 Use of cryptography')],
    findings: [{ resource: 'acme-alerts-topic', detail: 'Server-side encryption is off' }] },
  { id: 'EC-01', title: 'Caches encrypt what they store', severity: 'medium', status: 'not_applicable',
    detail: 'No ElastiCache clusters in this account.', remediation: '',
    references: [ref('uk_gdpr', 'Art. 32(1)(a) encryption of personal data'), ref('iso27001', 'A.8.24 Use of cryptography')],
    findings: [] },
  { id: 'EKS-01', title: 'Kubernetes API endpoints are not open to the whole internet', severity: 'high', status: 'not_applicable',
    detail: 'No EKS clusters in this account.', remediation: '',
    references: [ref('cyber_essentials', 'Firewalls and internet gateways'), ref('iso27001', 'A.8.20 Network security')],
    findings: [] },
  { id: 'CF-01', title: 'CloudFront serves over HTTPS only', severity: 'medium', status: 'pass',
    detail: 'Both distributions redirect viewers to HTTPS.', remediation: '',
    references: [ref('uk_gdpr', 'Art. 32(1)(a) encryption of personal data in transit'), ref('cyber_essentials', 'Secure configuration'), ref('iso27001', 'A.8.24 Use of cryptography')],
    findings: [] },
  { id: 'LAM-01', title: 'Functions run supported language runtimes', severity: 'medium', status: 'pass',
    detail: 'All 9 functions run supported runtimes.', remediation: '',
    references: [ref('cyber_essentials', 'Security update management'), ref('uk_gdpr', 'Art. 32(1)(b) ongoing security of processing systems'), ref('iso27001', 'A.8.8 Management of technical vulnerabilities')],
    findings: [] },
  { id: 'CFG-01', title: 'AWS Config rules are passing', severity: 'medium', status: 'unknown',
    detail: 'AWS Config is not switched on in this account, so this was never read. It is not counted as a pass.',
    remediation: 'Switch on AWS Config in each region you use, then add the rules that match your own policy.',
    references: [ref('uk_gdpr', 'Art. 32(1)(d) testing and assessing security measures'), ref('iso27001', 'A.8.9 Configuration management')],
    findings: [] },
  { id: 'SH-01', title: 'No open critical Security Hub findings', severity: 'high', status: 'unknown',
    detail: 'Security Hub is not switched on in this account, so this was never read. It is not counted as a pass.',
    remediation: 'Switch on Security Hub in your home region to collect findings across the account.',
    references: [ref('uk_gdpr', 'Art. 32(1)(d) testing and assessing security measures'), ref('iso27001', 'A.5.26 Response to information security incidents')],
    findings: [] },
  { id: 'RES-03', title: 'Load balancers span at least two availability zones', severity: 'medium', status: 'pass',
    detail: 'Both load balancers span two zones.', remediation: '',
    references: [ref('fca_ps21_3', 'Resilience of the entry point to an important business service'), ref('iso27001', 'A.8.14 Redundancy of information processing facilities')],
    findings: [] },
  { id: 'RES-04', title: 'CloudWatch alarms are configured', severity: 'medium', status: 'fail',
    detail: 'No CloudWatch alarms are configured in this account.',
    remediation: 'Create alarms for the things that would breach your impact tolerance first: database CPU and storage, load balancer 5xx responses, and queue age.',
    references: [ref('fca_ps21_3', 'Detecting an incident in time to stay within impact tolerance'), ref('iso27001', 'A.8.16 Monitoring activities')],
    findings: [{ resource: 'CloudWatch', detail: '0 alarms configured' }] },
]

function scoreFrameworks(controls: ComplianceControl[]): ComplianceFramework[] {
  return Object.entries(COMPLIANCE_FRAMEWORK_NAMES).map(([id, name]) => {
    const relevant = controls.filter(c => c.references.some(r => r.framework === id))
    const passed = relevant.filter(c => c.status === 'pass').length
    const failed = relevant.filter(c => c.status === 'fail').length
    const unknown = relevant.filter(c => c.status === 'unknown').length
    const evaluated = passed + failed
    const scope = id === 'fca_ps21_3' ? { scope: 'technical_evidence_only', scope_note: PS21_3_SCOPE_NOTE } : {}
    return { id, name, score: evaluated ? Math.round((100 * passed) / evaluated) : null, passed, failed, unknown, total: relevant.length, ...scope }
  })
}

const ICO_ADVANCED: ExposureReference = {
  id: 'ico_advanced_2025', kind: 'enforcement_case',
  label: 'Advanced Computer Software Group Ltd, £3,070,000',
  summary: 'Fined in March 2025 after attackers reached systems through a customer account that had no multi-factor authentication. Personal data of 79,404 people was put at risk.',
  source: 'https://ico.org.uk/action-weve-taken/enforcement/2025/03/advanced-computer-software-group-limited/',
  published: 'March 2025', amount_low: 3070000, amount_high: 3070000,
}

const ICO_DPP: ExposureReference = {
  id: 'ico_dpp_law_2025', kind: 'enforcement_case',
  label: 'DPP Law Ltd, £60,000',
  summary: 'A law firm fined in April 2025 for infringing Articles 5(1)(f), 32(1), 32(2) and 33(1). Attackers entered through an infrequently used administrator account with no multi-factor authentication, and the breach was reported 43 days after it was discovered.',
  source: 'https://ico.org.uk/action-weve-taken/enforcement/2025/04/dpp-law-ltd/',
  published: 'April 2025', amount_low: 60000, amount_high: 60000,
}

const CE_PLUS: ExposureReference = {
  id: 'ce_plus_assessment', kind: 'direct_cost',
  label: 'Cyber Essentials Plus assessment, about £2,000 to £3,000',
  summary: 'IASME, which runs the scheme for the NCSC, puts a Cyber Essentials Plus assessment at roughly £2,000 to £3,000 depending on the size and complexity of the network. A failed control means paying this again.',
  source: 'https://iasme.co.uk/articles/cyber-essentials-and-cyber-essentials-plus-what-is-the-difference/',
  published: 'IASME published guidance', amount_low: 2000, amount_high: 3000,
}

const GDPR_HIGHER_MAX: ExposureReference = {
  id: 'ukgdpr_higher_max', kind: 'statutory_maximum',
  label: 'Up to £17.5m or 4% of annual worldwide turnover, whichever is higher',
  summary: 'The higher maximum, which applies to breaches of the data protection principles in Article 5, including the integrity and confidentiality principle in Article 5(1)(f).',
  source: 'https://ico.org.uk/about-the-ico/our-information/policies-and-procedures/data-protection-fining-guidance/statutory-background/the-maximum-amount-of-a-fine-under-uk-gdpr-and-dpa-2018/',
  published: 'ICO data protection fining guidance', amount_low: null, amount_high: 17500000,
}

export const MOCK_EXPOSURE: Exposure = {
  failing_controls: 9,
  controls_with_published_exposure: 3,
  direct_cost: { low: 2000, high: 3000, display: '£2,000 to £3,000', references: [CE_PLUS] },
  comparable_enforcement: { low: 60000, high: 3070000, display: '£60,000 to £3.07m', references: [ICO_DPP, ICO_ADVANCED] },
  statutory_maximum: { display: GDPR_HIGHER_MAX.label, references: [GDPR_HIGHER_MAX] },
  items: [
    { control_id: 'IAM-01', control_title: 'Every IAM user with a password uses MFA', severity: 'high',
      why: 'An account without MFA is the exact entry route in both ICO cases below.',
      references: [ICO_ADVANCED, ICO_DPP, CE_PLUS] },
    { control_id: 'S3-01', control_title: 'S3 buckets block public access', severity: 'high',
      why: 'A bucket open to the internet is the clearest form of a confidentiality failure. If personal data is in it, this is a reportable breach.',
      references: [GDPR_HIGHER_MAX] },
    { control_id: 'GD-02', control_title: 'No open high or critical GuardDuty findings', severity: 'high',
      why: 'Open high-severity findings are the state DPP Law was in: something was wrong and nobody acted, so the 72-hour clock was missed.',
      references: [ICO_DPP] },
  ],
  basis:
    'Figures are published sources only: the statutory maximum set out by the ICO, ICO penalty notices ' +
    'for the same failing, and the certification body\'s own prices. They are not a prediction. A fine ' +
    'depends on turnover, on what you do after an incident, and on the Commissioner\'s discretion, none ' +
    'of which can be read from AWS settings.',
}

export const MOCK_COMPLIANCE: ComplianceReport = {
  evaluated_at: minsAgo(1),
  frameworks: scoreFrameworks(DEMO_CONTROLS),
  controls: DEMO_CONTROLS,
  exposure: MOCK_EXPOSURE,
  disclaimer:
    'These are automated checks of the AWS technical controls TekWatch can see. ' +
    'They help you gather evidence and spot gaps. They are not a certification, an audit, or legal advice.',
}

export const MOCK_EVIDENCE: EvidenceLog = {
  total_recorded: 6,
  anchors: 1,
  statement:
    'Each entry is chained to the one before it with SHA-256, so any later edit to a stored entry ' +
    'breaks every hash after it. Once a day the head of the chain is sent to an independent ' +
    'timestamping authority, which returns a signed RFC 3161 token proving the chain existed at ' +
    'that time. You can check a token yourself with openssl, without TekWatch.',
  verification: { intact: true, entries_checked: 6, broken_at: null, anchors: 1, last_anchored_at: minsAgo(5) },
  entries: [
    { seq: 6, recorded_at: minsAgo(5), kind: 'anchor',
      summary: 'Chain anchored with an independent timestamp from https://freetsa.org/tsr',
      hash: '1c7e4a9b2f0d6853ae1b4c7d9f2036a5c8e1b4d7f0a3c6e9b2d5f8a1c4e7b0d3',
      prev_hash: '9f2c41ab6d0e77b2c4f1a8e3d5b0c6971e2a4d8f3b7c5e1a9d0f6b2c8e4a7d31' },
    { seq: 5, recorded_at: minsAgo(6), kind: 'snapshot', summary: 'Compliance assessment: 11 passed, 9 failed',
      hash: '9f2c41ab6d0e77b2c4f1a8e3d5b0c6971e2a4d8f3b7c5e1a9d0f6b2c8e4a7d31', prev_hash: '4b7e0c2a9d1f6538e7c4b0a2d9f31e68c5a7b4d2f0e916c3a8d5b7f1e2c4a609' },
    { seq: 4, recorded_at: hoursAgo(5), kind: 'resolved', summary: 'S3-02 now passes: S3 buckets encrypt what they store',
      hash: '4b7e0c2a9d1f6538e7c4b0a2d9f31e68c5a7b4d2f0e916c3a8d5b7f1e2c4a609', prev_hash: 'd18a6f3b0c9e25471fa8d3b6c0e947215d8f3a0b6c2e419d7a5f0b3c8e6d2417' },
    { seq: 3, recorded_at: hoursAgo(28), kind: 'regressed', summary: 'RES-02 started failing: Databases keep automated backups',
      hash: 'd18a6f3b0c9e25471fa8d3b6c0e947215d8f3a0b6c2e419d7a5f0b3c8e6d2417', prev_hash: '72c5e0a9b3d1f846207e5c3a9d0b6f184e2a7c5d3b0f916e8a4d2c7b5f1e3a08' },
    { seq: 2, recorded_at: hoursAgo(29), kind: 'snapshot', summary: 'Compliance assessment: 11 passed, 9 failed',
      hash: '72c5e0a9b3d1f846207e5c3a9d0b6f184e2a7c5d3b0f916e8a4d2c7b5f1e3a08', prev_hash: '0a3f7d2c8b5e19406d3a7f2c9b0e5184d7a3c0f6b2e918d5a7c4f0b3e6d2a915' },
    { seq: 1, recorded_at: hoursAgo(53), kind: 'snapshot', summary: 'Compliance assessment: 11 passed, 9 failed',
      hash: '0a3f7d2c8b5e19406d3a7f2c9b0e5184d7a3c0f6b2e918d5a7c4f0b3e6d2a915', prev_hash: '0000000000000000000000000000000000000000000000000000000000000000' },
  ],
}

export const MOCK_CALENDAR: RegulatoryCalendar = {
  generated_at: minsAgo(1),
  overdue: 0,
  due_within_14_days: 2,
  awaiting_your_date: 1,
  entries: [
    { id: 'ico-72h:s3-exposure:acme-marketing-assets', kind: 'deadline',
      title: 'Decide whether the ICO must be told about acme-marketing-assets',
      due_at: hoursAhead(69), days_remaining: 2, overdue: false, urgency: 'soon',
      detail: 'Article 33 gives you 72 hours from becoming aware of a personal data breach to tell the ICO, unless it is unlikely to risk people\'s rights. If no personal data was exposed, record that decision and why.',
      framework: 'UK GDPR',
      source: 'https://ico.org.uk/for-organisations/report-a-breach/personal-data-breach/',
      action: 'Check what was in it, decide, and write the decision down either way.' },
    { id: 'cert-expiry:arn:cert', kind: 'expiry', title: 'TLS certificate for app.acme.co.uk expires',
      due_at: daysAhead(11), days_remaining: 11, overdue: false, urgency: 'soon',
      detail: 'An expired certificate stops the service and breaks encryption in transit. Certificates issued by ACM renew themselves only while the validation records are still in place.',
      framework: 'UK GDPR', source: null,
      action: 'Confirm the DNS validation records still exist so ACM can renew it.' },
    { id: 'renewal:cyber_essentials_expires_at', kind: 'renewal', title: 'Cyber Essentials certification expires',
      due_at: daysAhead(96), days_remaining: 96, overdue: false, urgency: 'scheduled',
      detail: 'Certification lasts twelve months. Most buyers who ask for it check the date.',
      framework: 'Cyber Essentials', source: null, action: null },
    { id: 'renewal:ico_fee_due_at', kind: 'renewal', title: 'ICO data protection fee due',
      due_at: null, days_remaining: null, overdue: false, urgency: 'unknown',
      detail: 'Most organisations that process personal data must pay the ICO every year. Add your date and TekWatch will track it.',
      framework: 'UK GDPR', source: null, action: 'Set the date on your profile.' },
  ],
}

export const MOCK_INCIDENTS: Incident[] = [
  {
    id: 's3-exposure:acme-marketing-assets',
    type: 's3_public_exposure',
    title: 'acme-marketing-assets was exposed by DeleteBucketPublicAccessBlock',
    severity: 'critical',
    correlated: true,
    summary: 'deploy-bot changed the access settings of acme-marketing-assets with DeleteBucketPublicAccessBlock, and the bucket no longer blocks public access.',
    detected_at: hoursAgo(3),
    affected: [{ service: 'S3', resource: 'acme-marketing-assets', region: 'eu-west-2' }],
    chain: [
      { service: 'CloudTrail', time: hoursAgo(3), detail: 'DeleteBucketPublicAccessBlock on acme-marketing-assets by deploy-bot from 91.108.xx.xx.' },
      { service: 'S3', time: minsAgo(4), detail: 'acme-marketing-assets no longer has S3 Block Public Access fully enabled.' },
    ],
    regulatory_impact: [
      { framework: 'UK GDPR', reference: 'Art. 32 Security of processing', why: 'A bucket that does not block public access is not an appropriate technical measure for personal data.' },
      { framework: 'UK GDPR', reference: 'Art. 33 Notification of a personal data breach', why: 'If this bucket holds personal data and was accessed while exposed, the ICO must be told within 72 hours of you becoming aware, unless the breach is unlikely to result in a risk to individuals.' },
      { framework: 'Cyber Essentials', reference: 'Secure configuration', why: 'Cloud storage must not be left reachable by the public by default.' },
    ],
    service_impact: {
      total: 1,
      summary: 'Related resources: it is published to the internet by CloudFront distribution cdn.acme.co.uk.',
      serves: [{ key: 'cloudfront:E1ACME', service: 'cloudfront', resource_id: 'E1ACME',
                 name: 'cdn.acme.co.uk', region: 'global', relationship: 'serves', confidence: 'direct',
                 why: 'This distribution serves acme-marketing-assets as an origin.' }],
      reachable_from: [],
      runs_in: [],
    },
    operational_impact: {
      headline: 'Public access is no longer prevented on acme-marketing-assets',
      points: [
        'The bucket holds 1,240 objects.',
        'That is 3.0 GB of data.',
        'Block Public Access is what stops a policy or ACL from granting access to everyone. With it off, such a grant now takes effect.',
      ],
    },
    remediation: [
      { order: 1, action: 'Block public access on the bucket now.', command: 'aws s3api put-public-access-block --bucket acme-marketing-assets --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true' },
      { order: 2, action: "Review the bucket's policy and ACL for grants to everyone.", command: 'aws s3api get-bucket-policy --bucket acme-marketing-assets && aws s3api get-bucket-acl --bucket acme-marketing-assets' },
      { order: 3, action: 'Confirm with deploy-bot that the change was authorised. If it was not, rotate their credentials.', command: null },
      { order: 4, action: 'Check whether the bucket holds personal data.', command: null },
      { order: 5, action: 'If it does, check access logs for the exposure window and decide whether the ICO must be notified within 72 hours.', command: 'aws cloudtrail lookup-events --lookup-attributes AttributeKey=ResourceName,AttributeValue=acme-marketing-assets' },
    ],
  },
]

// ─── Cost ─────────────────────────────────────────────────────────────────────

export function getMockCostSummary(timeRange: TimeRange) {
  return {
    mtd_total: 2891.40,
    last_month_total: 4247.80,
    forecasted_monthly: 4180.00,
    // What AWS bills the account in. The sample account is billed in dollars,
    // the way most AWS accounts are, and the page follows the data.
    currency: 'USD',
    daily_costs: genDailyCosts(timeRange, 142, 28, 77),
  }
}

export const MOCK_COST_SUMMARY = getMockCostSummary('24h')

export const MOCK_COST_BREAKDOWN = {
  breakdown: [
    { aws_service: 'Amazon EC2',        mtd_cost: 1080.40, vs_last_month: -4.2, pct: 37.4 },
    { aws_service: 'Amazon RDS',        mtd_cost: 620.80,  vs_last_month: 1.8,  pct: 21.5 },
    { aws_service: 'Amazon CloudFront', mtd_cost: 340.20,  vs_last_month: 12.4, pct: 11.8 },
    { aws_service: 'Amazon S3',         mtd_cost: 220.60,  vs_last_month: 6.1,  pct: 7.6  },
    { aws_service: 'AWS Lambda',        mtd_cost: 180.30,  vs_last_month: 38.7, pct: 6.2  },
    { aws_service: 'Amazon ECS',        mtd_cost: 160.40,  vs_last_month: -1.2, pct: 5.5  },
    { aws_service: 'Amazon SQS',        mtd_cost: 48.20,   vs_last_month: 2.4,  pct: 1.7  },
    { aws_service: 'AWS Secrets Mgr',   mtd_cost: 24.10,   vs_last_month: 0,    pct: 0.8  },
    { aws_service: 'Amazon SNS',        mtd_cost: 12.40,   vs_last_month: -0.8, pct: 0.4  },
    { aws_service: 'Other',             mtd_cost: 204.00,  vs_last_month: -2.1, pct: 7.1  },
  ],
}

// ─── Alerts ───────────────────────────────────────────────────────────────────

export const MOCK_ALERTS = [
  {
    alert_id: 'ALT-001',
    severity: 'critical' as const,
    status: 'active' as const,
    type: 'threshold',
    service: 'EC2',
    resource: 'web-server-01',
    description: 'CPU utilisation is 92.4% on web-server-01, exceeding the 80% critical threshold for 15+ minutes.',
    triggered_at: minsAgo(15),
    current_value: 92.4,
    threshold_value: 80,
    recommendation: 'Scale out the web tier — add a second t3.large instance or enable Auto Scaling. Review recent deployments for memory leaks or inefficient queries.',
  },
  {
    alert_id: 'ALT-002',
    severity: 'warning' as const,
    status: 'active' as const,
    type: 'threshold',
    service: 'RDS',
    resource: 'prod-db-01 (Aurora MySQL)',
    description: 'Active DB connections (187) is approaching the max_connections limit (210). Connection pool is 89% exhausted.',
    triggered_at: minsAgo(42),
    current_value: 187,
    threshold_value: 180,
    recommendation: 'Enable RDS Proxy to pool and reuse connections. Review application connection pool settings — consider adding connection pooling at the app layer.',
  },
  {
    alert_id: 'ALT-003',
    severity: 'warning' as const,
    status: 'active' as const,
    type: 'ai_anomaly',
    service: 'Lambda',
    resource: 'acme-image-processor',
    description: 'Anomaly detected: cold-start (init) duration for acme-image-processor averaged 3.4 s over the last hour, 6.1 standard deviations above its 7-day baseline of 0.8 s.',
    triggered_at: hoursAgo(2),
    current_value: 3400,
    threshold_value: 800,
    recommendation: 'Investigate recent dependency changes to the acme-image-processor package. Consider enabling Lambda SnapStart or provisioned concurrency. Check for oversized deployment packages.',
  },
  {
    alert_id: 'ALT-004',
    severity: 'warning' as const,
    status: 'acknowledged' as const,
    type: 'threshold',
    service: 'S3',
    resource: 'acme-static-website',
    description: 'S3 bucket acme-static-website has public access enabled. This may expose data and fails the Cyber Essentials secure configuration control.',
    triggered_at: hoursAgo(6),
    current_value: 1,
    threshold_value: 0,
    recommendation: 'Enable S3 Block Public Access at the bucket level. Use CloudFront with OAI for public website delivery instead of direct S3 public access.',
  },
  {
    alert_id: 'ALT-005',
    severity: 'critical' as const,
    status: 'acknowledged' as const,
    type: 'security',
    service: 'GuardDuty',
    resource: 'IAM user: deploy-bot',
    description: 'GuardDuty HIGH finding: API calls from a known malicious IP. Potential credential compromise of deploy-bot IAM user.',
    triggered_at: hoursAgo(2),
    current_value: 3,
    threshold_value: 0,
    recommendation: 'Immediately rotate the deploy-bot IAM access keys. Review CloudTrail for all API calls made by this user in the last 24 hours. Consider disabling the user until investigation is complete.',
  },
]

// ─── Agent ────────────────────────────────────────────────────────────────────

export const MOCK_AGENT = {
  customer_id: 'TT-0042',
  version: '1.4.2',
  status: 'healthy' as const,
  last_heartbeat: minsAgo(2),
  collection_interval_s: 300,
  regions: ['eu-west-2', 'eu-west-1', 'us-east-1'],
  metrics_collected_total: 2_840_421,
  uptime_hours: 2184,
  collectors: [
    { name: 'EC2',          status: 'ok', last_run: minsAgo(4),  resources: 12, metrics_sent: 288  },
    { name: 'RDS',          status: 'ok', last_run: minsAgo(4),  resources: 3,  metrics_sent: 72   },
    { name: 'Lambda',       status: 'ok', last_run: minsAgo(4),  resources: 6,  metrics_sent: 144  },
    { name: 'ECS',          status: 'ok', last_run: minsAgo(4),  resources: 6,  metrics_sent: 96   },
    { name: 'S3',           status: 'ok', last_run: minsAgo(9),  resources: 8,  metrics_sent: 64   },
    { name: 'SQS',          status: 'ok', last_run: minsAgo(4),  resources: 5,  metrics_sent: 60   },
    { name: 'SNS',          status: 'ok', last_run: minsAgo(4),  resources: 4,  metrics_sent: 32   },
    { name: 'CloudFront',   status: 'ok', last_run: minsAgo(9),  resources: 2,  metrics_sent: 24   },
    { name: 'GuardDuty',    status: 'ok', last_run: minsAgo(4),  resources: 2,  metrics_sent: 8    },
    { name: 'IAM',          status: 'ok', last_run: minsAgo(14), resources: 42, metrics_sent: 42   },
    { name: 'CloudWatch',   status: 'ok', last_run: minsAgo(4),  resources: 5,  metrics_sent: 30   },
    { name: 'Cost Explorer',status: 'ok', last_run: minsAgo(59), resources: 1,  metrics_sent: 12   },
    { name: 'DynamoDB',     status: 'ok', last_run: minsAgo(4),  resources: 4,  metrics_sent: 48   },
    { name: 'ElastiCache',  status: 'ok', last_run: minsAgo(4),  resources: 2,  metrics_sent: 32   },
    { name: 'ELB',          status: 'ok', last_run: minsAgo(4),  resources: 4,  metrics_sent: 64   },
    { name: 'Route53',      status: 'ok', last_run: minsAgo(9),  resources: 3,  metrics_sent: 12   },
    { name: 'VPC',          status: 'ok', last_run: minsAgo(9),  resources: 3,  metrics_sent: 18   },
    { name: 'ACM',          status: 'ok', last_run: minsAgo(59), resources: 4,  metrics_sent: 4    },
  ],
}

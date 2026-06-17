/**
 * Mock data for the admin portal's demo mode (no backend).
 *
 * Shapes mirror the real Tek Watch admin API responses exactly (see
 * api/routers/admin/*), so pages render unchanged. The story matches Tek
 * Tribe's actual commercial model — UK SME customers across the foundation /
 * growth / scale / enterprise tiers (see the business plan in memory).
 *
 * Timestamps are computed relative to "now" at call time so "last seen" and
 * "created" always read sensibly in the demo.
 */

const minsAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString()
const daysAgo = (d: number) => new Date(Date.now() - d * 86_400_000).toISOString()

export interface DemoCustomer {
  customer_id: string
  name: string
  email: string
  subscription_tier: string
  aws_account_ids: string[]
  status: string
  agent_status: string
  last_agent_seen: string | null
  created_at: string
}

const CUSTOMERS: DemoCustomer[] = [
  {
    customer_id: 'TT-0001', name: 'Caledonia Retail Group', email: 'cloudops@caledoniaretail.co.uk',
    subscription_tier: 'scale', aws_account_ids: ['481516234299', '622309128844'],
    status: 'active', agent_status: 'healthy', last_agent_seen: minsAgo(3), created_at: daysAgo(214),
  },
  {
    customer_id: 'TT-0002', name: 'Northbridge Fintech Ltd', email: 'platform@northbridge.io',
    subscription_tier: 'enterprise', aws_account_ids: ['730021554188', '901244537610', '118923004471'],
    status: 'active', agent_status: 'healthy', last_agent_seen: minsAgo(2), created_at: daysAgo(167),
  },
  {
    customer_id: 'TT-0003', name: 'Tay Valley Logistics', email: 'it@tayvalley.co.uk',
    subscription_tier: 'growth', aws_account_ids: ['556677889900'],
    status: 'active', agent_status: 'warning', last_agent_seen: minsAgo(14), created_at: daysAgo(98),
  },
  {
    customer_id: 'TT-0004', name: 'Granite City Media', email: 'devops@granitecitymedia.com',
    subscription_tier: 'foundation', aws_account_ids: ['204815162342'],
    status: 'active', agent_status: 'healthy', last_agent_seen: minsAgo(5), created_at: daysAgo(56),
  },
  {
    customer_id: 'TT-0005', name: 'Lothian HealthTech', email: 'security@lothianhealthtech.nhs.uk',
    subscription_tier: 'scale', aws_account_ids: ['677889900112', '335577991133'],
    status: 'active', agent_status: 'offline', last_agent_seen: minsAgo(47), created_at: daysAgo(132),
  },
  {
    customer_id: 'TT-0006', name: 'Clyde Marine Services', email: 'ops@clydemarine.co.uk',
    subscription_tier: 'growth', aws_account_ids: ['889900112233'],
    status: 'active', agent_status: 'healthy', last_agent_seen: minsAgo(1), created_at: daysAgo(41),
  },
  {
    customer_id: 'TT-0007', name: 'Pentland Software Co', email: 'admin@pentlandsoftware.dev',
    subscription_tier: 'foundation', aws_account_ids: ['990011223344'],
    status: 'suspended', agent_status: 'offline', last_agent_seen: daysAgo(6), created_at: daysAgo(73),
  },
  {
    customer_id: 'TT-0008', name: 'Aberdeen Energy Analytics', email: 'cloud@aberdeenenergy.com',
    subscription_tier: 'enterprise', aws_account_ids: ['112233445566', '223344556677'],
    status: 'active', agent_status: 'healthy', last_agent_seen: minsAgo(4), created_at: daysAgo(189),
  },
]

const DEFAULT_THRESHOLDS = [
  { service: 'ec2', metric_name: 'cpu_utilization_percent', operator: 'gt', threshold_value: 85, severity: 'high' },
  { service: 'rds', metric_name: 'cpu_utilization_percent', operator: 'gt', threshold_value: 80, severity: 'high' },
  { service: 'rds', metric_name: 'storage_used_percent', operator: 'gt', threshold_value: 90, severity: 'critical' },
  { service: 'rds', metric_name: 'database_connections', operator: 'gt', threshold_value: 100, severity: 'medium' },
  { service: 'lambda', metric_name: 'error_rate_percent', operator: 'gt', threshold_value: 5, severity: 'high' },
  { service: 'sqs', metric_name: 'messages_visible', operator: 'gt', threshold_value: 1000, severity: 'medium' },
  { service: 'sqs', metric_name: 'oldest_message_age_seconds', operator: 'gt', threshold_value: 3600, severity: 'high' },
  { service: 'elasticache', metric_name: 'cpu_utilization_percent', operator: 'gt', threshold_value: 75, severity: 'medium' },
  { service: 'elasticache', metric_name: 'cache_hit_ratio_percent', operator: 'lt', threshold_value: 80, severity: 'medium' },
]

const DEMO_API_KEY = 'tw_demo_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6'

export const demoData = {
  listCustomers: () => ({ customers: CUSTOMERS }),

  getCustomer: (customerId: string) => ({
    customer: CUSTOMERS.find(c => c.customer_id === customerId) ?? {
      ...CUSTOMERS[0], customer_id: customerId,
    },
  }),

  createCustomer: (data: { name: string; subscription_tier: string }) => {
    const n = CUSTOMERS.length + 1
    return {
      customer_id: `TT-${String(n).padStart(4, '0')}`,
      name: data.name,
      subscription_tier: data.subscription_tier,
      api_key: DEMO_API_KEY,
    }
  },

  rotateApiKey: () => ({ new_api_key: DEMO_API_KEY }),

  getDefaultThresholds: () => ({
    thresholds: DEFAULT_THRESHOLDS.map(t => ({
      PK: 'DEFAULT',
      SK: `${t.service}#${t.metric_name}`,
      enabled: true,
      ...t,
    })),
  }),

  getCustomerThresholds: () => ({ thresholds: [] }),

  upsertThreshold: () => ({ ok: true }),

  getOperationsHealth: () => {
    const active = CUSTOMERS.filter(c => c.status === 'active')
    return {
      ingest_queue: { depth: 12, dlq_depth: 0, oldest_message_age_seconds: 4 },
      api_service: { status: 'healthy', uptime_seconds: 1_247_400 },
      ingest_consumer: { status: 'running', messages_processed_1h: 18_432, messages_failed_1h: 0 },
      customers: {
        total: CUSTOMERS.length,
        active: active.length,
        agents_healthy: CUSTOMERS.filter(c => c.agent_status === 'healthy').length,
        agents_offline: CUSTOMERS.filter(c => c.agent_status === 'offline').length,
      },
      recent_errors: [
        { timestamp: minsAgo(38), service: 'ingest-consumer', message: 'Transient DynamoDB throttling on metrics table (retried, succeeded)' },
      ],
    }
  },

  cfnTemplate: (customerId: string) =>
    `# Tek Watch Agent — CloudFormation template (DEMO)\n` +
    `# Customer: ${customerId}\n` +
    `AWSTemplateFormatVersion: '2010-09-09'\n` +
    `Description: Deploys the Tek Watch monitoring agent (demo placeholder)\n`,
}

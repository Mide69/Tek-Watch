/**
 * Admin Portal API client — communicates with the Tribe Watch API admin endpoints.
 */
import axios, { AxiosInstance, AxiosError } from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

class AdminAPIClient {
  private client: AxiosInstance
  private token: string | null = null

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' },
    })

    this.client.interceptors.request.use((config) => {
      const t = this.getToken()
      if (t) config.headers.Authorization = `Bearer ${t}`
      return config
    })

    this.client.interceptors.response.use(
      (r) => r,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          this.clearToken()
          if (typeof window !== 'undefined') window.location.href = '/login'
        }
        return Promise.reject(error)
      }
    )
  }

  setToken(token: string) {
    this.token = token
    if (typeof window !== 'undefined') localStorage.setItem('tw_admin_token', token)
  }

  getToken(): string | null {
    if (!this.token && typeof window !== 'undefined')
      this.token = localStorage.getItem('tw_admin_token')
    return this.token
  }

  clearToken() {
    this.token = null
    if (typeof window !== 'undefined') localStorage.removeItem('tw_admin_token')
  }

  // ── Customers ──────────────────────────────────────────────────────────────

  async listCustomers() {
    const r = await this.client.get('/api/v1/admin/customers')
    return r.data
  }

  async getCustomer(customerId: string) {
    const r = await this.client.get(`/api/v1/admin/customers/${customerId}`)
    return r.data
  }

  async createCustomer(data: {
    name: string
    email: string
    subscription_tier: string
    aws_account_ids: string[]
  }) {
    const r = await this.client.post('/api/v1/admin/customers', data)
    return r.data
  }

  async updateCustomer(customerId: string, data: Record<string, unknown>) {
    const r = await this.client.put(`/api/v1/admin/customers/${customerId}`, data)
    return r.data
  }

  async rotateApiKey(customerId: string) {
    const r = await this.client.post(`/api/v1/admin/customers/${customerId}/rotate-key`)
    return r.data
  }

  async downloadCfnTemplate(customerId: string): Promise<Blob> {
    const r = await this.client.get(
      `/api/v1/admin/customers/${customerId}/cfn-template`,
      { responseType: 'blob' }
    )
    return r.data
  }

  // ── Thresholds ─────────────────────────────────────────────────────────────

  async getDefaultThresholds() {
    const r = await this.client.get('/api/v1/admin/thresholds')
    return r.data
  }

  async getCustomerThresholds(customerId: string) {
    const r = await this.client.get(`/api/v1/admin/thresholds/${customerId}`)
    return r.data
  }

  async upsertThreshold(
    customerId: string,
    service: string,
    metricName: string,
    config: Record<string, unknown>
  ) {
    const r = await this.client.put(`/api/v1/admin/thresholds/${customerId}`, {
      service,
      metric_name: metricName,
      ...config,
    })
    return r.data
  }

  // ── Operations ─────────────────────────────────────────────────────────────

  async getOperationsHealth() {
    const r = await this.client.get('/api/v1/admin/operations')
    return r.data
  }
}

const adminApi = new AdminAPIClient()
export default adminApi

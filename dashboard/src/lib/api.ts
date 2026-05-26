/**
 * API client for Tek Watch backend.
 * Handles authentication, request/response formatting, and error handling.
 */

import axios, { AxiosInstance, AxiosError } from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

class APIClient {
  private client: AxiosInstance
  private token: string | null = null

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Request interceptor - add JWT token
    this.client.interceptors.request.use(
      (config) => {
        if (this.token) {
          config.headers.Authorization = `Bearer ${this.token}`
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    // Response interceptor - handle errors
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          // Token expired or invalid - redirect to login
          this.clearToken()
          if (typeof window !== 'undefined') {
            window.location.href = '/login'
          }
        }
        return Promise.reject(error)
      }
    )
  }

  setToken(token: string) {
    this.token = token
    if (typeof window !== 'undefined') {
      localStorage.setItem('tek_watch_token', token)
    }
  }

  getToken(): string | null {
    if (!this.token && typeof window !== 'undefined') {
      this.token = localStorage.getItem('tek_watch_token')
    }
    return this.token
  }

  clearToken() {
    this.token = null
    if (typeof window !== 'undefined') {
      localStorage.removeItem('tek_watch_token')
    }
  }

  // Overview
  async getOverview(region?: string) {
    const params = region ? { region } : {}
    const response = await this.client.get('/api/v1/overview', { params })
    return response.data
  }

  // Compute
  async getEC2Instances(region?: string) {
    const params = region ? { region } : {}
    const response = await this.client.get('/api/v1/compute/ec2', { params })
    return response.data
  }

  async getLambdaFunctions(region?: string) {
    const params = region ? { region } : {}
    const response = await this.client.get('/api/v1/compute/lambda', { params })
    return response.data
  }

  async getECSServices(region?: string) {
    const params = region ? { region } : {}
    const response = await this.client.get('/api/v1/compute/ecs', { params })
    return response.data
  }

  // Databases
  async getRDSInstances(region?: string) {
    const params = region ? { region } : {}
    const response = await this.client.get('/api/v1/databases/rds', { params })
    return response.data
  }

  async getDynamoDBTables(region?: string) {
    const params = region ? { region } : {}
    const response = await this.client.get('/api/v1/databases/dynamodb', { params })
    return response.data
  }

  // Storage
  async getS3Buckets(region?: string) {
    const params = region ? { region } : {}
    const response = await this.client.get('/api/v1/storage/s3', { params })
    return response.data
  }

  // Networking
  async getVPCResources(region?: string) {
    const params = region ? { region } : {}
    const response = await this.client.get('/api/v1/networking/vpc', { params })
    return response.data
  }

  async getLoadBalancers(region?: string) {
    const params = region ? { region } : {}
    const response = await this.client.get('/api/v1/networking/elb', { params })
    return response.data
  }

  async getCloudFrontDistributions() {
    const response = await this.client.get('/api/v1/networking/cloudfront')
    return response.data
  }

  async getRoute53HealthChecks() {
    const response = await this.client.get('/api/v1/networking/route53')
    return response.data
  }

  // Messaging
  async getSQSQueues(region?: string) {
    const params = region ? { region } : {}
    const response = await this.client.get('/api/v1/messaging/sqs', { params })
    return response.data
  }

  async getSNSTopics(region?: string) {
    const params = region ? { region } : {}
    const response = await this.client.get('/api/v1/messaging/sns', { params })
    return response.data
  }

  // Security
  async getGuardDutyFindings(severity?: string) {
    const params = severity ? { severity } : {}
    const response = await this.client.get('/api/v1/security/guardduty', { params })
    return response.data
  }

  async getIAMSummary() {
    const response = await this.client.get('/api/v1/security/iam')
    return response.data
  }

  async getACMCertificates() {
    const response = await this.client.get('/api/v1/security/acm')
    return response.data
  }

  async getCloudWatchAlarms(region?: string) {
    const params = region ? { region } : {}
    const response = await this.client.get('/api/v1/security/alarms', { params })
    return response.data
  }

  // Cost
  async getCostSummary() {
    const response = await this.client.get('/api/v1/cost/summary')
    return response.data
  }

  async getCostBreakdown() {
    const response = await this.client.get('/api/v1/cost/breakdown')
    return response.data
  }

  // Alerts
  async getAlerts(statusFilter?: string) {
    const params = statusFilter ? { status_filter: statusFilter } : {}
    const response = await this.client.get('/api/v1/alerts', { params })
    return response.data
  }

  async acknowledgeAlert(alertId: string) {
    const response = await this.client.put(`/api/v1/alerts/${alertId}/acknowledge`)
    return response.data
  }

  // Agent
  async getAgentHealth() {
    const response = await this.client.get('/api/v1/agent/health')
    return response.data
  }

  // Metrics (time-series)
  async getResourceMetrics(
    resourceId: string,
    metricName: string,
    timeRange: '24h' | '7d' | '30d' | '90d' = '24h'
  ) {
    const response = await this.client.get(`/api/v1/metrics/${resourceId}`, {
      params: { metric_name: metricName, time_range: timeRange },
    })
    return response.data
  }
}

// Singleton instance
const apiClient = new APIClient()

export default apiClient

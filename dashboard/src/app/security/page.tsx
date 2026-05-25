'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Shield, Key, AlertTriangle, CheckCircle, Clock, Users } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { MOCK_GUARDDUTY, MOCK_IAM, MOCK_ACM_CERTS, MOCK_CW_ALARMS } from '@/lib/mockData'
import { formatRelativeTime } from '@/lib/utils'

function SeverityBadge({ severity }: { severity: string }) {
  const s = severity.toUpperCase()
  if (s === 'CRITICAL' || s === 'HIGH') return <Badge variant="error">{s}</Badge>
  if (s === 'MEDIUM') return <Badge variant="warning">{s}</Badge>
  return <Badge variant="info">{s}</Badge>
}

function AlarmBadge({ state }: { state: string }) {
  if (state === 'ALARM') return <Badge variant="error">ALARM</Badge>
  if (state === 'OK') return <Badge variant="success">OK</Badge>
  return <Badge variant="default">{state}</Badge>
}

export default function SecurityPage() {
  const { loading: authLoading } = useAuth()

  if (authLoading) return (
    <DashboardLayout>
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500" />
      </div>
    </DashboardLayout>
  )

  return (
    <DashboardLayout>
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-white">Security</h1>
          <p className="text-slate-400 text-sm mt-0.5">GuardDuty · IAM · ACM · CloudWatch Alarms</p>
        </div>

        {/* Top row - summary tiles */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'GuardDuty Findings', value: MOCK_GUARDDUTY.length, color: 'text-red-400',     bg: 'bg-red-500/10 border-red-500/20',     icon: AlertTriangle },
            { label: 'Users w/o MFA',      value: MOCK_IAM.users_without_mfa, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20', icon: Users },
            { label: 'Old Access Keys',    value: MOCK_IAM.old_access_keys,   color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20', icon: Key },
            { label: 'Certs Expiring <30d',value: MOCK_ACM_CERTS.filter(c => c.days_remaining < 30).length, color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20', icon: Shield },
          ].map(s => (
            <Card key={s.label}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-slate-400">{s.label}</span>
                  <div className={`w-7 h-7 rounded-lg border flex items-center justify-center ${s.bg}`}>
                    <s.icon className={`w-3.5 h-3.5 ${s.color}`} />
                  </div>
                </div>
                <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* GuardDuty */}
        <section>
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">GuardDuty Findings</h2>
          <div className="space-y-3">
            {MOCK_GUARDDUTY.map(f => (
              <Card key={f.id} className="border-amber-500/20 bg-amber-500/5">
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap mb-1.5">
                        <SeverityBadge severity={f.severity} />
                        <span className="text-xs font-mono text-slate-400">{f.type.split(':')[0]}</span>
                        <span className="text-xs text-slate-500">{f.region}</span>
                      </div>
                      <p className="text-sm font-medium text-white mb-1">{f.title}</p>
                      <p className="text-xs text-slate-400 leading-relaxed mb-2">{f.description}</p>
                      <div className="flex items-center gap-4 text-xs text-slate-500">
                        <span>{f.count} occurrences</span>
                        <span>First: {formatRelativeTime(f.first_seen)}</span>
                        <span>Last: {formatRelativeTime(f.last_seen)}</span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        {/* IAM + ACM side by side */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* IAM Health */}
          <section>
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">IAM Health</h2>
            <Card>
              <CardContent className="p-4 space-y-3">
                {[
                  { label: 'Total IAM users',       value: MOCK_IAM.users_total,          ok: true },
                  { label: 'Users without MFA',     value: MOCK_IAM.users_without_mfa,    ok: MOCK_IAM.users_without_mfa === 0 },
                  { label: 'Old access keys (>90d)',value: MOCK_IAM.old_access_keys,       ok: MOCK_IAM.old_access_keys === 0 },
                  { label: 'Unused roles (>90d)',   value: MOCK_IAM.unused_roles,          ok: MOCK_IAM.unused_roles === 0 },
                  { label: 'Root MFA enabled',      value: MOCK_IAM.root_mfa_enabled ? 'Yes' : 'No', ok: MOCK_IAM.root_mfa_enabled },
                  { label: 'Root access keys',      value: MOCK_IAM.root_access_keys ? 'Present' : 'None', ok: !MOCK_IAM.root_access_keys },
                ].map(item => (
                  <div key={item.label} className="flex items-center justify-between py-1.5 border-b border-white/[0.04] last:border-0">
                    <span className="text-sm text-slate-300">{item.label}</span>
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-semibold ${item.ok ? 'text-emerald-400' : 'text-amber-400'}`}>{item.value}</span>
                      {item.ok
                        ? <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                        : <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </section>

          {/* ACM Certs */}
          <section>
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">ACM Certificates</h2>
            <Card>
              <CardContent className="p-4 space-y-3">
                {MOCK_ACM_CERTS.map(cert => (
                  <div key={cert.domain} className="flex items-center justify-between py-1.5 border-b border-white/[0.04] last:border-0">
                    <div>
                      <p className="text-sm font-medium text-slate-200">{cert.domain}</p>
                      <p className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                        <Clock className="w-3 h-3" />
                        {cert.days_remaining} days remaining
                      </p>
                    </div>
                    {cert.days_remaining < 30
                      ? <Badge variant="warning">Expiring</Badge>
                      : <Badge variant="success">Valid</Badge>}
                  </div>
                ))}
              </CardContent>
            </Card>
          </section>
        </div>

        {/* CloudWatch Alarms */}
        <section>
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">CloudWatch Alarms</h2>
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06]">
                      {['Alarm Name', 'State', 'Namespace', 'Metric'].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {MOCK_CW_ALARMS.map((a, idx) => (
                      <tr key={a.name} className={`border-b border-white/[0.04] hover:bg-white/[0.02] ${idx % 2 ? 'bg-white/[0.01]' : ''}`}>
                        <td className="px-4 py-3 font-medium text-white">{a.name}</td>
                        <td className="px-4 py-3"><AlarmBadge state={a.state} /></td>
                        <td className="px-4 py-3 text-xs font-mono text-slate-400">{a.namespace}</td>
                        <td className="px-4 py-3 text-xs text-slate-400">{a.metric}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </DashboardLayout>
  )
}

'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { Shield, Key, AlertTriangle, CheckCircle, Clock, Users } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useDashboard, TIME_RANGE_LABELS } from '@/contexts/DashboardContext'
import { useSecurity } from '@/hooks/useData'
import { formatRelativeTime } from '@/lib/utils'

function SeverityBadge({ severity }: { severity: string }) {
  const s = severity.toUpperCase()
  if (s === 'CRITICAL' || s === 'HIGH') return <Badge variant="error">{s}</Badge>
  if (s === 'MEDIUM')                   return <Badge variant="warning">{s}</Badge>
  return <Badge variant="info">{s}</Badge>
}

function AlarmBadge({ state }: { state: string }) {
  if (state === 'ALARM') return <Badge variant="error">ALARM</Badge>
  if (state === 'OK')    return <Badge variant="success">OK</Badge>
  return <Badge variant="default">{state}</Badge>
}

function ComplianceBar({ label, score }: { label: string; score: number }) {
  const color = score >= 90 ? 'bg-emerald-500' : score >= 75 ? 'bg-amber-500' : 'bg-red-500'
  const text  = score >= 90 ? 'text-emerald-600 dark:text-emerald-600 dark:text-emerald-400' : score >= 75 ? 'text-amber-500 dark:text-amber-400' : 'text-red-500 dark:text-red-400'
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm text-foreground">{label}</span>
        <span className={`text-sm font-bold ${text}`}>{score}%</span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-700`} style={{ width: `${score}%` }} />
      </div>
    </div>
  )
}

export default function SecurityPage() {
  const { customerId }      = useAuth()
  const { timeRange }       = useDashboard()
  const { data, isLoading } = useSecurity()

  if (isLoading || !data) {
    return (
      <DashboardLayout customerId={customerId || undefined}>
        <div className="space-y-6">
          <div className="h-8 w-32 bg-muted rounded animate-pulse" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[0,1,2,3].map(i => <CardSkeleton key={i} />)}
          </div>
        </div>
      </DashboardLayout>
    )
  }

  const { guardduty, iam, certs, alarms, compliance } = data
  const expiringCerts = certs.filter(c => c.days_to_expiry < 30).length

  return (
    <DashboardLayout customerId={customerId || undefined}>
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Security</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            GuardDuty · IAM · ACM · CloudWatch Alarms · {TIME_RANGE_LABELS[timeRange]}
          </p>
        </div>

        {/* Summary tiles */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'GuardDuty Findings', value: guardduty.length,         color: 'text-red-500 dark:text-red-400',     bg: 'bg-red-500/10 border-red-500/20',     icon: AlertTriangle },
            { label: 'Users w/o MFA',      value: iam.users_without_mfa,    color: 'text-amber-500 dark:text-amber-400',   bg: 'bg-amber-500/10 border-amber-500/20', icon: Users },
            { label: 'Old Access Keys',    value: iam.old_access_keys,      color: 'text-amber-500 dark:text-amber-400',   bg: 'bg-amber-500/10 border-amber-500/20', icon: Key },
            { label: 'Certs Expiring <30d',value: expiringCerts,            color: expiringCerts > 0 ? 'text-red-500 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-600 dark:text-emerald-400', bg: expiringCerts > 0 ? 'bg-red-500/10 border-red-500/20' : 'bg-emerald-500/10 border-emerald-500/20', icon: Shield },
          ].map(s => (
            <Card key={s.label}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-muted-foreground">{s.label}</span>
                  <div className={`w-7 h-7 rounded-lg border flex items-center justify-center ${s.bg}`}>
                    <s.icon className={`w-3.5 h-3.5 ${s.color}`} />
                  </div>
                </div>
                <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Compliance Scores — time-range-aware */}
        <Card className="border-indigo-500/20 bg-primary/5">
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-semibold text-foreground">Compliance Posture</h3>
                <p className="text-xs text-muted-foreground mt-0.5">{TIME_RANGE_LABELS[timeRange]} snapshot</p>
              </div>
              <Badge variant="info">4 frameworks</Badge>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <ComplianceBar label="GDPR"           score={compliance.gdpr} />
              <ComplianceBar label="Cyber Essentials" score={compliance.cyber_essentials} />
              <ComplianceBar label="FCA"            score={compliance.fca} />
              <ComplianceBar label="ISO 27001"      score={compliance.iso27001} />
            </div>
            <p className="text-xs text-muted-foreground mt-3">
              Scores reflect findings across {TIME_RANGE_LABELS[timeRange].toLowerCase()}. Longer ranges may show historical regressions.
            </p>
          </CardContent>
        </Card>

        {/* GuardDuty */}
        <section>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">GuardDuty Findings</h2>
          <div className="space-y-3">
            {guardduty.map(f => (
              <Card key={f.finding_id} className="border-amber-500/20 bg-amber-500/5">
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap mb-1.5">
                        <SeverityBadge severity={f.severity} />
                        <span className="text-xs font-mono text-muted-foreground">{f.type.split(':')[0]}</span>
                        <span className="text-xs text-muted-foreground">{f.region}</span>
                      </div>
                      <p className="text-sm font-medium text-foreground mb-1">{f.type.split('/')[1] || f.type}</p>
                      <p className="text-xs text-muted-foreground leading-relaxed mb-2">{f.description}</p>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span>{f.count} occurrences</span>
                        <span>Updated: {formatRelativeTime(f.updated_at)}</span>
                        <span className="font-mono">{f.resource}</span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        {/* IAM + ACM */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* IAM Health */}
          <section>
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">IAM Health</h2>
            <Card>
              <CardContent className="p-4 space-y-3">
                {[
                  { label: 'Total IAM users',            value: iam.users_total,          ok: true },
                  { label: 'Users without MFA',          value: iam.users_without_mfa,    ok: iam.users_without_mfa === 0 },
                  { label: 'Old access keys (>90d)',      value: iam.old_access_keys,      ok: iam.old_access_keys === 0 },
                  { label: 'Overprivileged roles',        value: iam.overprivileged_roles, ok: iam.overprivileged_roles === 0 },
                  { label: 'Unused credentials (>90d)',   value: iam.unused_credentials_90d, ok: iam.unused_credentials_90d === 0 },
                  { label: 'Root MFA enabled',           value: iam.root_mfa_enabled ? 'Yes' : 'No', ok: iam.root_mfa_enabled },
                  { label: 'Root access keys active',    value: iam.root_access_keys ? 'Present' : 'None', ok: !iam.root_access_keys },
                ].map(item => (
                  <div key={item.label} className="flex items-center justify-between py-1.5 border-b border-border/40 last:border-0">
                    <span className="text-sm text-foreground">{item.label}</span>
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-semibold ${item.ok ? 'text-emerald-600 dark:text-emerald-600 dark:text-emerald-400' : 'text-amber-500 dark:text-amber-400'}`}>{item.value}</span>
                      {item.ok
                        ? <CheckCircle className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                        : <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </section>

          {/* ACM Certs */}
          <section>
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">ACM Certificates</h2>
            <Card>
              <CardContent className="p-4 space-y-3">
                {certs.map(cert => (
                  <div key={cert.domain} className="flex items-center justify-between py-1.5 border-b border-border/40 last:border-0">
                    <div>
                      <p className="text-sm font-medium text-foreground">{cert.domain}</p>
                      <p className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                        <Clock className="w-3 h-3" />
                        {cert.days_to_expiry} days remaining
                        {!cert.auto_renew && <span className="text-amber-400 ml-1">· manual renewal</span>}
                      </p>
                    </div>
                    {cert.days_to_expiry < 30
                      ? <Badge variant="warning">Expiring Soon</Badge>
                      : <Badge variant="success">Valid</Badge>}
                  </div>
                ))}
              </CardContent>
            </Card>
          </section>
        </div>

        {/* CloudWatch Alarms */}
        <section>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">CloudWatch Alarms</h2>
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      {['Alarm Name', 'State', 'Namespace', 'Metric', 'Threshold', 'Value'].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-medium text-muted-foreground whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {alarms.map((a, idx) => (
                      <tr key={a.alarm_name} className={`border-b border-border/40 hover:bg-muted/30 ${idx % 2 ? 'bg-muted/10' : ''}`}>
                        <td className="px-4 py-3 font-medium text-foreground">{a.alarm_name}</td>
                        <td className="px-4 py-3"><AlarmBadge state={a.state} /></td>
                        <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{a.namespace}</td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">{a.metric}</td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">{a.threshold}</td>
                        <td className="px-4 py-3 text-xs">
                          <span className={a.state === 'ALARM' ? 'text-red-400 font-semibold' : 'text-foreground'}>
                            {a.value}
                          </span>
                        </td>
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

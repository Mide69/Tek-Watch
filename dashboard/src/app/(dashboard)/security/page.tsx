'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { Shield, ShieldAlert, Key, AlertTriangle, CheckCircle, HelpCircle, Clock, Users } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useDashboard, TIME_RANGE_LABELS } from '@/contexts/DashboardContext'
import { useSecurity } from '@/hooks/useData'
import { formatRelativeTime, fmtCount, DASH } from '@/lib/utils'
import { COMPLIANCE_FRAMEWORK_NAMES, type ComplianceControl, type Incident } from '@/lib/mockData'

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

/** A null score means no check for this framework could be evaluated yet. */
function ComplianceBar({ label, score, sub }: { label: string; score: number | null; sub: string }) {
  const color = score == null ? 'bg-muted-foreground/30' : score >= 90 ? 'bg-emerald-500' : score >= 75 ? 'bg-amber-500' : 'bg-red-500'
  const text  = score == null ? 'text-muted-foreground' : score >= 90 ? 'text-emerald-600 dark:text-emerald-400' : score >= 75 ? 'text-amber-500 dark:text-amber-400' : 'text-red-500 dark:text-red-400'
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm text-foreground">{label}</span>
        <span className={`text-sm font-bold ${text}`}>{score == null ? DASH : `${score}%`}</span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-700`} style={{ width: `${score ?? 0}%` }} />
      </div>
      <p className="text-[11px] text-muted-foreground mt-1">{sub}</p>
    </div>
  )
}

function ControlRow({ control }: { control: ComplianceControl }) {
  return (
    <details className="group rounded-lg border border-border bg-background/60 px-3 py-2.5">
      <summary className="flex items-center gap-2 cursor-pointer list-none">
        <SeverityBadge severity={control.severity} />
        <span className="text-sm text-foreground flex-1">{control.title}</span>
        <span className="text-[11px] font-mono text-muted-foreground">{control.id}</span>
      </summary>
      <div className="mt-3 space-y-2 text-xs text-muted-foreground leading-relaxed">
        <p>{control.detail}</p>
        {control.findings.length > 0 && (
          <ul className="space-y-1">
            {control.findings.map(f => (
              <li key={`${f.resource}-${f.detail}`}>
                <span className="font-mono text-foreground">{f.resource}</span>: {f.detail}
              </li>
            ))}
          </ul>
        )}
        {control.remediation && (
          <p><span className="font-medium text-foreground">How to fix: </span>{control.remediation}</p>
        )}
        <p className="text-[11px]">
          {control.references.map(r => `${COMPLIANCE_FRAMEWORK_NAMES[r.framework] ?? r.framework} ${r.reference}`).join(' · ')}
        </p>
      </div>
    </details>
  )
}

function IncidentCard({ incident }: { incident: Incident }) {
  const critical = incident.severity === 'critical'
  return (
    <Card className={critical ? 'border-red-500/30 bg-red-500/5' : 'border-amber-500/20 bg-amber-500/5'}>
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <ShieldAlert className={`w-4 h-4 mt-0.5 flex-shrink-0 ${critical ? 'text-red-400' : 'text-amber-400'}`} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1.5">
              <SeverityBadge severity={incident.severity} />
              {!incident.correlated && <Badge variant="default">Cause not in CloudTrail history</Badge>}
              {incident.detected_at && (
                <span className="text-xs text-muted-foreground">{formatRelativeTime(incident.detected_at)}</span>
              )}
            </div>
            <p className="text-sm font-medium text-foreground mb-1">{incident.title}</p>
            <p className="text-xs text-muted-foreground leading-relaxed">{incident.summary}</p>

            <details className="mt-3">
              <summary className="text-xs font-medium text-primary cursor-pointer">
                What happened, what it means, and how to fix it
              </summary>
              <div className="mt-3 space-y-4 text-xs">
                <div>
                  <h4 className="font-semibold text-foreground mb-1.5">What happened</h4>
                  <ol className="space-y-1.5 border-l border-border pl-3">
                    {incident.chain.map((step, i) => (
                      <li key={i} className="text-muted-foreground">
                        <span className="font-medium text-foreground">{step.service}</span>
                        {step.time && <span> · {formatRelativeTime(step.time)}</span>}
                        <br />{step.detail}
                      </li>
                    ))}
                  </ol>
                </div>
                {incident.operational_impact && (
                  <div>
                    <h4 className="font-semibold text-foreground mb-1.5">
                      {incident.operational_impact.headline}
                    </h4>
                    <ul className="space-y-1.5">
                      {incident.operational_impact.points.map(p => (
                        <li key={p} className="text-muted-foreground">{p}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <div>
                  <h4 className="font-semibold text-foreground mb-1.5">Why it matters</h4>
                  <ul className="space-y-1.5">
                    {incident.regulatory_impact.map(r => (
                      <li key={`${r.framework}-${r.reference}`} className="text-muted-foreground">
                        <span className="font-medium text-foreground">{r.framework} {r.reference}.</span> {r.why}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="font-semibold text-foreground mb-1.5">What to do, in order</h4>
                  <ol className="space-y-2">
                    {incident.remediation.map(step => (
                      <li key={step.order} className="text-muted-foreground">
                        <span className="font-medium text-foreground">{step.order}.</span> {step.action}
                        {step.command && (
                          <pre className="mt-1 overflow-x-auto rounded-md bg-muted px-2.5 py-1.5 font-mono text-[11px] text-foreground"><code>{step.command}</code></pre>
                        )}
                      </li>
                    ))}
                  </ol>
                </div>
              </div>
            </details>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * The shell — sidebar, Home, Sign out — depends only on who is signed in,
 * never on security data, so it renders even when the content below throws.
 * See the identical note in networking/page.tsx for why this split exists.
 */
export default function SecurityPage() {
  const { customerId } = useAuth()
  return (
    <DashboardLayout customerId={customerId || undefined}>
      <ErrorBoundary>
        <SecurityContent />
      </ErrorBoundary>
    </DashboardLayout>
  )
}

function SecurityContent() {
  const { timeRange } = useDashboard()
  const { data } = useSecurity()

  if (!data) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-32 bg-muted rounded animate-pulse" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[0,1,2,3].map(i => <CardSkeleton key={i} />)}
        </div>
      </div>
    )
  }

  const { guardduty, iam, certs, alarms, compliance, incidents } = data
  const failing = compliance.controls.filter(c => c.status === 'fail')
  const unmeasured = compliance.controls.filter(c => c.status === 'unknown')
  // days_to_expiry is null for a cert the agent has not yet reported on — that
  // is not the same as expiring, and counting it as such would put an unissued
  // or not-yet-collected certificate in the same "act now" bucket as one two
  // days from lapsing.
  const expiringCerts = certs.filter(c => c.days_to_expiry != null && c.days_to_expiry < 30).length

  // IAM Health rows. `ok` is deliberately three-valued: true (checked, clean),
  // false (checked, a finding), or null (never measured). iam.root_access_keys
  // and several others are not collected by any agent yet, and rendering a
  // missing value as "No" / "None" reads as a confident, checked answer —
  // exactly the kind of invented-looking figure the rest of this rewrite exists
  // to get rid of. A dash with a neutral icon says, correctly, "not measured."
  const iamRows: Array<{ label: string; value: string; ok: boolean | null }> = [
    { label: 'Total IAM users',           value: fmtCount(iam.users_total),        ok: true },
    { label: 'Users without MFA',         value: fmtCount(iam.users_without_mfa),  ok: iam.users_without_mfa == null ? null : iam.users_without_mfa === 0 },
    { label: 'Old access keys (>90d)',    value: fmtCount(iam.old_access_keys),    ok: iam.old_access_keys == null ? null : iam.old_access_keys === 0 },
    { label: 'Overprivileged roles',      value: fmtCount(iam.overprivileged_roles),      ok: iam.overprivileged_roles == null ? null : iam.overprivileged_roles === 0 },
    { label: 'Unused credentials (>90d)', value: fmtCount(iam.unused_credentials_90d),    ok: iam.unused_credentials_90d == null ? null : iam.unused_credentials_90d === 0 },
    { label: 'Root MFA enabled',          value: iam.root_mfa_enabled == null ? DASH : (iam.root_mfa_enabled ? 'Yes' : 'No'), ok: iam.root_mfa_enabled },
    { label: 'Root access keys active',   value: iam.root_access_keys == null ? DASH : (iam.root_access_keys ? 'Present' : 'None'), ok: iam.root_access_keys == null ? null : !iam.root_access_keys },
  ]

  return (
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Security</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            Incidents · Compliance checks · GuardDuty · IAM · ACM · CloudWatch Alarms · {TIME_RANGE_LABELS[timeRange]}
          </p>
        </div>

        {/* Summary tiles */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'GuardDuty Findings', value: guardduty.length,         color: 'text-red-500 dark:text-red-400',     bg: 'bg-red-500/10 border-red-500/20',     icon: AlertTriangle },
            { label: 'Users w/o MFA',      value: fmtCount(iam.users_without_mfa),    color: 'text-amber-500 dark:text-amber-400',   bg: 'bg-amber-500/10 border-amber-500/20', icon: Users },
            { label: 'Old Access Keys',    value: fmtCount(iam.old_access_keys),      color: 'text-amber-500 dark:text-amber-400',   bg: 'bg-amber-500/10 border-amber-500/20', icon: Key },
            { label: 'Certs Expiring <30d',value: expiringCerts,            color: expiringCerts > 0 ? 'text-red-500 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400', bg: expiringCerts > 0 ? 'bg-red-500/10 border-red-500/20' : 'bg-emerald-500/10 border-emerald-500/20', icon: Shield },
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

        {/* Correlated incidents */}
        <section>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-1">Incidents</h2>
          <p className="text-xs text-muted-foreground mb-3">
            Changes recorded in CloudTrail, matched to what they did to your resources.
          </p>
          <div className="space-y-3">
            {incidents.length === 0 && (
              <p className="text-sm text-muted-foreground">No incidents found.</p>
            )}
            {incidents.map(i => <IncidentCard key={i.id} incident={i} />)}
          </div>
        </section>

        {/* Compliance checks */}
        <Card className="border-indigo-500/20 bg-primary/5">
          <CardContent className="p-5">
            <div className="flex items-start justify-between gap-3 mb-4">
              <div>
                <h3 className="font-semibold text-foreground">Compliance checks</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {compliance.controls.length > 0
                    ? `${compliance.controls.length} automated checks of your AWS configuration, based on the latest agent data`
                    : 'Checks run as soon as the agent reports.'}
                </p>
              </div>
              {compliance.frameworks.length > 0 && <Badge variant="info">{compliance.frameworks.length} frameworks</Badge>}
            </div>

            {compliance.frameworks.length === 0 ? (
              <p className="text-sm text-muted-foreground">No compliance data yet.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {compliance.frameworks.map(fw => (
                  <ComplianceBar
                    key={fw.id}
                    label={fw.name}
                    score={fw.score}
                    sub={
                      fw.passed + fw.failed === 0
                        ? 'Not measured yet'
                        : `${fw.passed} of ${fw.passed + fw.failed} checks passed${fw.unknown ? `, ${fw.unknown} not measured` : ''}`
                    }
                  />
                ))}
              </div>
            )}

            {failing.length > 0 && (
              <div className="mt-5 space-y-2">
                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Failing checks ({failing.length})
                </h4>
                {failing.map(c => <ControlRow key={c.id} control={c} />)}
              </div>
            )}

            {unmeasured.length > 0 && (
              <p className="text-xs text-muted-foreground mt-3">
                Not measured yet: {unmeasured.map(c => c.title).join('; ')}. These are left out of the scores,
                not counted as passed.
              </p>
            )}
            {compliance.disclaimer && (
              <p className="text-[11px] text-muted-foreground mt-3">{compliance.disclaimer}</p>
            )}
          </CardContent>
        </Card>

        {/* GuardDuty */}
        <section>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">GuardDuty Findings</h2>
          <div className="space-y-3">
            {guardduty.length === 0 && (
              <p className="text-sm text-muted-foreground">No findings reported.</p>
            )}
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
                {iamRows.map(item => (
                  <div key={item.label} className="flex items-center justify-between py-1.5 border-b border-border/40 last:border-0">
                    <span className="text-sm text-foreground">{item.label}</span>
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-semibold ${
                        item.ok == null ? 'text-muted-foreground' : item.ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-500 dark:text-amber-400'
                      }`}>{item.value}</span>
                      {item.ok == null
                        ? <HelpCircle className="w-3.5 h-3.5 text-muted-foreground" />
                        : item.ok
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
                {certs.length === 0 && (
                  <p className="text-sm text-muted-foreground">No certificates reported.</p>
                )}
                {certs.map(cert => (
                  <div key={cert.domain} className="flex items-center justify-between py-1.5 border-b border-border/40 last:border-0">
                    <div>
                      <p className="text-sm font-medium text-foreground">{cert.domain}</p>
                      <p className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                        <Clock className="w-3 h-3" />
                        {cert.days_to_expiry == null ? `${DASH} days remaining` : `${cert.days_to_expiry} days remaining`}
                        {/* auto_renew is never collected today — explicitly false, not merely
                            missing, is what should read as "manual renewal". */}
                        {cert.auto_renew === false && <span className="text-amber-400 ml-1">· manual renewal</span>}
                      </p>
                    </div>
                    {cert.days_to_expiry == null
                      ? <Badge variant="default">Unknown</Badge>
                      : cert.days_to_expiry < 30
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
                    {alarms.length === 0 && (
                      <tr><td colSpan={6} className="px-4 py-6 text-center text-sm text-muted-foreground">No alarms reported.</td></tr>
                    )}
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
  )
}

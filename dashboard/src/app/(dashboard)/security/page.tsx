'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { Shield, ShieldAlert, Key, AlertTriangle, CheckCircle, HelpCircle, Clock, Users, Scale, FileCheck, Download, Link2, CalendarClock, Network, RefreshCw } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useDashboard, TIME_RANGE_LABELS } from '@/contexts/DashboardContext'
import { useSecurity } from '@/hooks/useData'
import { formatRelativeTime, fmtCount, DASH } from '@/lib/utils'
import { COMPLIANCE_FRAMEWORK_NAMES, type CalendarEntry, type ComplianceControl, type ComplianceFramework, type EvidenceLog, type Exposure, type Incident, type RegulatoryCalendar, type ServiceImpactNode } from '@/lib/mockData'
import { useState } from 'react'
import axios from 'axios'
import apiClient from '@/lib/api'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

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

const URGENCY: Record<string, { variant: 'error' | 'warning' | 'info' | 'default'; label: string }> = {
  overdue:   { variant: 'error',   label: 'OVERDUE' },
  critical:  { variant: 'error',   label: 'TODAY' },
  soon:      { variant: 'warning', label: 'SOON' },
  scheduled: { variant: 'info',    label: 'SCHEDULED' },
  unknown:   { variant: 'default', label: 'NO DATE SET' },
}

function whenDue(entry: CalendarEntry): string {
  if (entry.days_remaining == null) return 'Date not set'
  if (entry.overdue) return `${Math.abs(entry.days_remaining)} days ago`
  if (entry.days_remaining === 0) return 'Today'
  return `In ${entry.days_remaining} day${entry.days_remaining === 1 ? '' : 's'}`
}

/**
 * Dates this account has to meet.
 *
 * Every row is driven by something real: a 72-hour clock started by an
 * exposure we actually saw, an expiry date AWS reported, or a renewal date the
 * customer gave us. A date nobody has told us stays blank and asks for it,
 * rather than becoming an invented reminder.
 */
function CalendarCard({ calendar }: { calendar: RegulatoryCalendar }) {
  if (!calendar || calendar.entries.length === 0) return null
  return (
    <Card className={calendar.overdue > 0 ? 'border-red-500/30 bg-red-500/5' : 'border-border'}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
          <div className="flex items-start gap-2">
            <CalendarClock className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-foreground">What is due</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Deadlines, expiries and renewals for this account
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {calendar.overdue > 0 && <Badge variant="error">{calendar.overdue} overdue</Badge>}
            {calendar.due_within_14_days > 0 && <Badge variant="warning">{calendar.due_within_14_days} within 14 days</Badge>}
          </div>
        </div>

        <div className="space-y-2">
          {calendar.entries.map(entry => {
            const urgency = URGENCY[entry.urgency] ?? URGENCY.unknown
            return (
              <details key={entry.id} className="rounded-lg border border-border bg-background/60 px-3 py-2.5">
                <summary className="flex items-center gap-2 cursor-pointer list-none flex-wrap">
                  <Badge variant={urgency.variant}>{urgency.label}</Badge>
                  <span className="text-sm text-foreground flex-1 min-w-0">{entry.title}</span>
                  <span className="text-[11px] text-muted-foreground">{whenDue(entry)}</span>
                </summary>
                <p className="mt-2 text-xs text-muted-foreground leading-relaxed">{entry.detail}</p>
                {entry.action && (
                  <p className="mt-1.5 text-xs text-foreground">{entry.action}</p>
                )}
                <p className="mt-1.5 text-[11px] text-muted-foreground">
                  {entry.framework}
                  {entry.source && (
                    <>
                      {' · '}
                      <a href={entry.source} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                        Read the rule
                      </a>
                    </>
                  )}
                </p>
              </details>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

/** What else a finding reaches, from the customer's own dependency graph. */
function ServiceImpactBlock({ nodes, heading }: { nodes: ServiceImpactNode[]; heading: string }) {
  if (!nodes || nodes.length === 0) return null
  return (
    <div>
      <h4 className="font-semibold text-foreground mb-1.5 flex items-center gap-1.5">
        <Network className="w-3.5 h-3.5 text-primary" />
        {heading}
      </h4>
      <ul className="space-y-1.5">
        {nodes.map(node => (
          <li key={node.key} className="text-muted-foreground">
            <span className="font-mono text-foreground">{node.name}</span>
            <span className="text-[11px] uppercase tracking-wider ml-2">
              {node.service} · {node.confidence}
            </span>
            <span className="block text-xs">{node.why}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * "I have fixed this, check now."
 *
 * The evidence recorder runs hourly, which is right for a log and wrong for
 * somebody who has just changed something. This asks the API to re-evaluate
 * against the agent's latest data and record whatever changed.
 */
function RecheckButton({ controlId, onResult }: { controlId: string; onResult: (status: string) => void }) {
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState('')

  async function recheck() {
    setBusy(true)
    setResult('')
    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/security/controls/${controlId}/recheck`,
        {},
        { headers: { Authorization: `Bearer ${apiClient.getToken()}` } },
      )
      const status = response.data?.control?.status ?? 'unknown'
      setResult(
        status === 'pass' ? 'Fixed. Recorded in your evidence log.'
        : status === 'fail' ? 'Still failing against your latest agent data.'
        : 'Not measurable yet. Give the agent one collection cycle.',
      )
      onResult(status)
    } catch {
      setResult('Could not check right now. Please try again shortly.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-2 flex items-center gap-2 flex-wrap">
      <button
        onClick={recheck}
        disabled={busy}
        className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-muted/40 disabled:opacity-50"
      >
        <RefreshCw className={`w-3.5 h-3.5 ${busy ? 'animate-spin' : ''}`} />
        {busy ? 'Checking…' : 'I have fixed this, check now'}
      </button>
      {result && <span className="text-xs text-muted-foreground">{result}</span>}
    </div>
  )
}

/**
 * What a failing control could cost, from published sources only.
 *
 * Three figures kept apart on purpose: what the law allows, what the ICO has
 * actually fined somebody for the same failing, and what the customer will
 * spend putting it right. Adding them together would produce one confident
 * number that means nothing. Every figure carries its source.
 */
function ExposureCard({ exposure }: { exposure: Exposure }) {
  if (!exposure || exposure.controls_with_published_exposure === 0) return null
  const bands = [
    { label: 'Cost to put right', value: exposure.direct_cost.display, refs: exposure.direct_cost.references, tone: 'text-foreground' },
    { label: 'Fined for the same failing', value: exposure.comparable_enforcement.display, refs: exposure.comparable_enforcement.references, tone: 'text-amber-600 dark:text-amber-400' },
    { label: 'Statutory maximum', value: exposure.statutory_maximum.display, refs: exposure.statutory_maximum.references, tone: 'text-muted-foreground' },
  ].filter(b => b.value)

  return (
    <Card className="border-amber-500/20 bg-amber-500/5">
      <CardContent className="p-5">
        <div className="flex items-start gap-2 mb-4">
          <Scale className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
          <div>
            <h3 className="font-semibold text-foreground">What this could cost you</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Based on {exposure.controls_with_published_exposure} of your {exposure.failing_controls} failing checks
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {bands.map(band => (
            <div key={band.label} className="rounded-lg border border-border bg-card/60 p-3">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{band.label}</p>
              <p className={`text-lg font-bold mt-1 ${band.tone}`}>{band.value}</p>
              <ul className="mt-2 space-y-1">
                {band.refs.map(r => (
                  <li key={r.id}>
                    <a href={r.source} target="_blank" rel="noopener noreferrer"
                       className="text-[11px] text-primary hover:underline inline-flex items-start gap-1">
                      <Link2 className="w-3 h-3 mt-0.5 flex-shrink-0" />
                      <span>{r.kind === 'statutory_maximum' ? r.published : r.label}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-4 space-y-2">
          {exposure.items.map(item => (
            <details key={item.control_id} className="rounded-lg border border-border bg-background/60 px-3 py-2.5">
              <summary className="flex items-center gap-2 cursor-pointer list-none">
                <span className="text-sm text-foreground flex-1">{item.control_title}</span>
                <span className="text-[11px] font-mono text-muted-foreground">{item.control_id}</span>
              </summary>
              <p className="mt-2 text-xs text-muted-foreground leading-relaxed">{item.why}</p>
              <ul className="mt-2 space-y-1.5">
                {item.references.map(r => (
                  <li key={r.id} className="text-xs text-muted-foreground leading-relaxed">
                    <a href={r.source} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                      {r.label}
                    </a>
                    <span className="text-[11px]"> · {r.published}</span>
                    {r.applies_to === 'fca_regulated' && (
                      <span className="text-[11px] text-amber-600 dark:text-amber-400"> · FCA-regulated firms only</span>
                    )}
                    <p className="text-[11px] mt-0.5">{r.summary}</p>
                  </li>
                ))}
              </ul>
            </details>
          ))}
        </div>

        <p className="text-[11px] text-muted-foreground mt-3 leading-relaxed">{exposure.basis}</p>
      </CardContent>
    </Card>
  )
}

const EVIDENCE_KIND: Record<string, { label: string; variant: 'success' | 'error' | 'info' | 'default' }> = {
  resolved: { label: 'RESOLVED', variant: 'success' },
  regressed: { label: 'REGRESSED', variant: 'error' },
  snapshot: { label: 'ASSESSED', variant: 'info' },
  anchor: { label: 'TIMESTAMPED', variant: 'default' },
}

/** The audit trail: what was assessed, what changed, and proof it is unedited. */
function EvidenceCard({ evidence }: { evidence: EvidenceLog }) {
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState('')
  const verification = evidence.verification

  async function download() {
    setError('')
    setDownloading(true)
    try {
      const response = await axios.get(`${API_BASE_URL}/api/v1/security/evidence/export`, {
        headers: { Authorization: `Bearer ${apiClient.getToken()}` },
        responseType: 'blob',
      })
      const url = URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.download = 'tekwatch-compliance-evidence.csv'
      link.click()
      URL.revokeObjectURL(url)
    } catch {
      setError('Could not prepare the file right now. Please try again shortly.')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
          <div className="flex items-start gap-2">
            <FileCheck className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-foreground">Compliance evidence</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                {evidence.total_recorded > 0
                  ? `${evidence.total_recorded} entries recorded. Every assessment and every change, in order.`
                  : 'Entries appear here once the agent has reported and the first assessment runs.'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {verification && (
              <Badge variant={verification.intact ? 'success' : 'error'}>
                {verification.intact
                  ? `CHAIN INTACT · ${verification.entries_checked} CHECKED`
                  : `BROKEN AT ENTRY ${verification.broken_at}`}
              </Badge>
            )}
            {verification?.anchors ? (
              <Badge variant="info">
                TIMESTAMPED {verification.last_anchored_at ? formatRelativeTime(verification.last_anchored_at) : ''}
              </Badge>
            ) : null}
            <button
              onClick={download}
              disabled={downloading || evidence.entries.length === 0}
              className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted/40 disabled:opacity-50"
            >
              <Download className="w-3.5 h-3.5" />
              {downloading ? 'Preparing…' : 'Download evidence'}
            </button>
          </div>
        </div>

        {error && <p className="text-sm text-red-500 dark:text-red-400 mb-3">{error}</p>}

        {evidence.entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing recorded yet.</p>
        ) : (
          <div className="space-y-2">
            {evidence.entries.slice(0, 8).map(entry => {
              const kind = EVIDENCE_KIND[entry.kind] ?? EVIDENCE_KIND.snapshot
              return (
                <div key={entry.seq} className="flex items-start gap-3 rounded-lg border border-border bg-background/60 px-3 py-2.5">
                  <Badge variant={kind.variant}>{kind.label}</Badge>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-foreground">{entry.summary}</p>
                    <p className="text-[11px] text-muted-foreground mt-0.5 font-mono truncate">
                      #{entry.seq} · {formatRelativeTime(entry.recorded_at)} · {entry.hash.slice(0, 16)}…
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        <p className="text-[11px] text-muted-foreground mt-3 leading-relaxed">{evidence.statement}</p>
      </CardContent>
    </Card>
  )
}

/** A null score means no check for this framework could be evaluated yet. */
function ComplianceBar({ label, score, sub, note }: { label: string; score: number | null; sub: string; note?: string }) {
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
      {note && (
        <details className="mt-1">
          <summary className="text-[11px] text-primary cursor-pointer hover:underline list-none">
            What this covers
          </summary>
          <p className="text-[11px] text-muted-foreground mt-1 leading-relaxed">{note}</p>
        </details>
      )}
    </div>
  )
}

function ControlRow({ control, recheckable = false }: { control: ComplianceControl; recheckable?: boolean }) {
  const [rechecked, setRechecked] = useState('')
  return (
    <details className="group rounded-lg border border-border bg-background/60 px-3 py-2.5">
      <summary className="flex items-center gap-2 cursor-pointer list-none">
        <SeverityBadge severity={control.severity} />
        <span className="text-sm text-foreground flex-1">{control.title}</span>
        <span className="text-[11px] font-mono text-muted-foreground">{control.id}</span>
      </summary>
      <div className="mt-3 space-y-2 text-xs text-muted-foreground leading-relaxed">
        <p>{control.detail}</p>
        {rechecked === 'pass' && (
          <p className="text-emerald-600 dark:text-emerald-400">This now passes.</p>
        )}
        {recheckable && <RecheckButton controlId={control.id} onResult={setRechecked} />}
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
                {incident.service_impact && incident.service_impact.total > 0 && (
                  <>
                    <ServiceImpactBlock
                      nodes={incident.service_impact.serves}
                      heading="What else this is wired to"
                    />
                    <ServiceImpactBlock
                      nodes={incident.service_impact.reachable_from}
                      heading="What can reach it"
                    />
                  </>
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

  const { guardduty, iam, certs, alarms, compliance, incidents, evidence, calendar } = data
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
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {compliance.frameworks.map((fw: ComplianceFramework) => (
                  <ComplianceBar
                    key={fw.id}
                    label={fw.name}
                    score={fw.score}
                    note={fw.scope_note}
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
                {failing.map(c => <ControlRow key={c.id} control={c} recheckable />)}
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

        {calendar && <CalendarCard calendar={calendar} />}

        {compliance.exposure && <ExposureCard exposure={compliance.exposure} />}

        {evidence && <EvidenceCard evidence={evidence} />}

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

'use client'

import { useState, useId, useEffect, useRef } from 'react'
import Link from 'next/link'
import { LogoMark } from '@/components/ui/Logo'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import {
  Radio, Activity, Shield, DollarSign, Zap, Server, Cpu, AlertTriangle,
  TrendingUp, TrendingDown, ShieldCheck, Cloud, GitMerge,
  ArrowRight, Check, ChevronDown, ChevronRight, Menu, X, Gavel, PoundSterling, BarChart3,
  Linkedin, Youtube, Mail, MapPin, Bot, Sparkles, Key, Users, MessageSquare,
} from 'lucide-react'
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  RadialBarChart, RadialBar, PolarAngleAxis, ReferenceDot, ReferenceLine,
  BarChart, Bar, Cell,
} from 'recharts'

/*
 * The marketing page commits to one light look (clean white, indigo accent)
 * whatever theme the dashboard is set to, so colours here are explicit
 * rather than theme tokens. The one exception is the product preview, which
 * sits inside a `.dark` frame so it reads as a screenshot of the real app.
 */

const TIP_STY = { borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)', background: '#0e1525', fontSize: 12, color: '#e2eaf4' }

const spendCurrent = [45, 52, 48, 61, 58, 70, 65, 72, 68, 75, 80, 73, 69, 78, 82, 88, 77, 74, 83, 91, 86, 79, 88, 95, 92, 88, 97, 105, 99, 112]
const spendPrevious = [40, 44, 43, 52, 50, 58, 56, 60, 59, 63, 66, 62, 60, 65, 68, 71, 66, 65, 69, 74, 71, 68, 73, 76, 75, 73, 77, 80, 78, 79]
const spendData = spendCurrent.map((v, i) => ({ day: i + 1, spend: v, prevSpend: spendPrevious[i] }))
const avgSpend = Math.round(spendCurrent.reduce((s, v) => s + v, 0) / spendCurrent.length)
const anomalyPoint = spendData[spendData.length - 1]

const scoreData = [{ name: 'score', value: 91, fill: '#818cf8' }]

const complianceFrameworks = [
  { label: 'UK GDPR', status: 'pass' as const },
  { label: 'Cyber Essentials', status: 'pass' as const },
  { label: 'ISO 27001:2022', status: 'pending' as const },
]

const serviceCostData = [
  { service: 'EC2', cost: 620 },
  { service: 'RDS', cost: 410 },
  { service: 'Lambda', cost: 280 },
  { service: 'S3', cost: 195 },
  { service: 'CloudFront', cost: 140 },
  { service: 'Other', cost: 195 },
]
const maxServiceCost = Math.max(...serviceCostData.map(d => d.cost))

const SERVICE_COLORS = ['#818cf8', '#a78bfa', '#38bdf8', '#fbbf24', '#f97316', '#34d399']
const DONUT_R = 62, DONUT_CX = 78, DONUT_CY = 78
const donutCirc = 2 * Math.PI * DONUT_R
const donutTotal = serviceCostData.reduce((s, d) => s + d.cost, 0)
const donutSegments = serviceCostData.reduce<{ frac: number; offset: number; color: string }[]>((acc, d, i) => {
  const frac = d.cost / donutTotal
  const offset = acc.length ? acc[acc.length - 1].offset + acc[acc.length - 1].frac : 0
  acc.push({ frac, offset, color: SERVICE_COLORS[i % SERVICE_COLORS.length] })
  return acc
}, [])

const guardDutyPreview = [
  { title: 'UnauthorizedAccess:IAMUser/ConsoleLoginSuccess.B', severity: 'MEDIUM', resource: 'IAM · admin-ci-user', age: '2h ago' },
  { title: 'Recon:EC2/PortProbeUnprotectedPort', severity: 'LOW', resource: 'EC2 · web-server-03', age: '1d ago' },
]

const compliancePreview = [
  { label: 'UK GDPR', score: 89 },
  { label: 'Cyber Essentials', score: 75 },
  { label: 'ISO 27001:2022', score: 80 },
]

const securitySummaryTiles = [
  { icon: AlertTriangle, label: 'GuardDuty Findings', value: '2', tone: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20' },
  { icon: Users, label: 'Users w/o MFA', value: '1', tone: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' },
  { icon: Key, label: 'Old Access Keys', value: '3', tone: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' },
  { icon: ShieldCheck, label: 'Certs Expiring <30d', value: '0', tone: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' },
]

const chatExchange = {
  question: 'Why did my AWS bill spike this week?',
  answer: 'Your spend jumped 18% on Tuesday, mostly EC2. Three on-demand instances in eu-west-2 have run at steady utilisation for 30 days straight; switching them to Reserved would save roughly £140/month.',
  tools: ['Cost breakdown', 'EC2 instances'],
}

const previewTabs = [
  { id: 'overview', label: 'Overview', path: '/overview' },
  { id: 'security', label: 'Security', path: '/security' },
  { id: 'cost', label: 'Cost', path: '/cost' },
  { id: 'assistant', label: 'AI Assistant', path: '/chat' },
] as const

type PreviewTabId = typeof previewTabs[number]['id']

const PLATFORM_LINKS = [
  { label: 'Real-time monitoring', href: '#capabilities', desc: '20+ AWS services, every region' },
  { label: 'Anomaly detection', href: '#platform', desc: 'Your own 7-day baseline' },
  { label: 'Compliance checks', href: '#capabilities', desc: 'UK GDPR, Cyber Essentials, ISO 27001' },
  { label: 'Incident correlation', href: '#platform', desc: 'Who changed what, and the fix' },
  { label: 'Cost intelligence', href: '#capabilities', desc: 'Spend trends and spikes' },
]

const FEATURES = [
  {
    icon: Activity,
    title: 'Real-time Visibility',
    desc: 'EC2, RDS, Lambda, ECS/EKS, S3, DynamoDB and 14 more AWS services, giving you full visibility across every active region from your first dashboard load.',
    points: ['20+ AWS services monitored', 'Every active region, day one', '90-day metric history'],
  },
  {
    icon: Zap,
    title: 'Anomaly Detection',
    desc: 'TekWatch builds a 7-day statistical baseline for every metric it collects and flags readings that break from it, with no thresholds to set. Each alert then comes with a plain-English explanation.',
    points: ['No thresholds to configure', 'Cost, performance & security', 'Plain-English explanations'],
  },
  {
    icon: Shield,
    title: 'UK Compliance Intelligence',
    desc: 'Automated checks of your AWS setup, mapped to the UK frameworks SMEs actually face, naming each failing resource and how to fix it.',
    points: ['UK GDPR, Cyber Essentials & ISO 27001', 'Incidents traced to who changed what', 'GuardDuty & Security Hub findings'],
  },
  {
    icon: DollarSign,
    title: 'Cost Intelligence',
    desc: 'MTD spend, 30-day trends, per-service breakdowns, and daily cost spikes flagged against your own baseline before the bill arrives.',
    points: ['Daily spend trends', 'Per-service breakdown', 'Cost spike alerts'],
  },
  {
    icon: Server,
    title: 'Managed Service Option',
    desc: "Don't want to DIY? Tek Tribe's own engineers monitor and manage it for you, from £500/month, with TekWatch included.",
    points: ['Continuous monitoring & patching', 'Compliance reporting included', 'Regular cost reviews'],
  },
  {
    icon: Radio,
    title: 'Lightweight Agent',
    desc: 'A single ECS Fargate task in your AWS account. Read-only IAM, outbound-only, zero firewall changes.',
    points: ['ECS Fargate', 'Read-only IAM role', 'Auto-deploy CloudFormation'],
  },
]

const ONBOARDING_STEPS = [
  {
    title: 'See it running instantly',
    desc: 'Launch the live demo, no signup or credit card needed. You will be looking at a fully populated sample dashboard within seconds.',
  },
  {
    title: 'Deploy in under 30 minutes',
    desc: 'When you are ready to connect your own AWS account, we hand you a pre-configured CloudFormation template for the read-only monitoring agent. No inbound firewall changes needed.',
  },
  {
    title: 'See what’s really going on',
    desc: 'Your dashboard fills with your own data from the agent’s first run: anomalies, compliance gaps and cost trends, all explained in plain English.',
  },
]

const statTiles = [
  { icon: Cpu, label: 'Monitored Resources', value: '847', delta: '+12%', good: true, sub: 'vs last month', trend: [620, 640, 655, 670, 690, 705, 720, 735, 760, 780, 810, 847] },
  { icon: AlertTriangle, label: 'Active Alerts', value: '3', delta: '−40%', good: true, sub: 'vs last week', trend: [9, 8, 8, 7, 6, 6, 5, 5, 4, 4, 3, 3] },
  { icon: DollarSign, label: 'Monthly AWS Spend', value: '£1,840', delta: '+4%', good: false, sub: 'vs last month', trend: [1650, 1700, 1680, 1720, 1750, 1690, 1730, 1760, 1740, 1780, 1810, 1840] },
]

const problemStats = [
  { icon: Gavel, value: '£43.2M', label: 'ICO fines issued in 2024 for data protection failures', source: 'ICO Annual Report, 2024–25' },
  { icon: PoundSterling, value: '£3,670', label: 'Average cost of a cyber incident for a UK SME', source: 'FSB Cyber Security Report, 2024' },
  { icon: BarChart3, value: '<5%', label: 'Of UK SMEs with cloud infrastructure use any paid monitoring tool', source: 'AWS Partner Network research, 2024' },
  { icon: TrendingUp, value: '29%', label: 'Year-on-year growth in Cyber Essentials Plus certifications', source: 'NCSC Annual Review, 2025' },
]

const pricingTiers = [
  {
    name: 'Starter', monthly: 79, discount: 0.10,
    desc: 'For micro-businesses, startups and charities getting started with AWS.',
    features: ['Up to 2 AWS accounts', '50 monitored resources', 'Anomaly detection', 'UK GDPR compliance checks'],
    highlight: false,
  },
  {
    name: 'Business', monthly: 199, discount: 0.10,
    desc: 'For growing SMEs, FinTech firms and professional services.',
    features: ['Up to 5 AWS accounts', '500 monitored resources', 'AI assistant + cost spike alerts', 'UK GDPR, Cyber Essentials & ISO 27001 checks', 'Email & Slack alerts'],
    highlight: true,
  },
  {
    name: 'Enterprise', monthly: 499, discount: 0.15,
    desc: 'For mid-market and regulated businesses with complex environments.',
    features: ['Unlimited accounts & resources', 'Incident reports with UK GDPR impact', 'Full API access', 'Dedicated 2-hour support'],
    highlight: false,
  },
]

// ─── Small building blocks ───────────────────────────────────────────────────

function Sparkline({ data, color }: { data: number[]; color: string }) {
  const w = 64, h = 24
  const gradientId = useId()
  const max = Math.max(...data), min = Math.min(...data), range = max - min || 1
  const coords = data.map((v, i) => [(i / (data.length - 1)) * w, h - ((v - min) / range) * h])
  const linePoints = coords.map(([x, y]) => `${x},${y}`).join(' ')
  const areaPoints = `0,${h} ${linePoints} ${w},${h}`
  const [lastX, lastY] = coords[coords.length - 1]
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-16 h-6" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={areaPoints} fill={`url(#${gradientId})`} stroke="none" />
      <polyline points={linePoints} fill="none" stroke={color} strokeWidth="1.5" strokeOpacity="0.85" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastX} cy={lastY} r="2.5" fill={color} stroke="#0e1525" strokeWidth="1.5" />
    </svg>
  )
}

/** Fires once when the element scrolls into view; stays true afterwards. */
function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [inView, setInView] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    // Reveal immediately where IntersectionObserver is unavailable. Revealed
    // content starts at opacity 0, so failing closed would leave the page
    // blank rather than merely unanimated.
    if (typeof IntersectionObserver === 'undefined') {
      setInView(true)
      return
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true)
          observer.disconnect()
        }
      },
      { threshold: 0.15, rootMargin: '0px 0px -80px 0px' }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  return [ref, inView] as const
}

/**
 * Fades a block up the first time it enters the viewport. prefers-reduced-motion
 * is handled globally in globals.css, which collapses the animation to ~0s.
 */
function Reveal({ children, delay = 0, className = '' }: { children: React.ReactNode; delay?: number; className?: string }) {
  const [ref, inView] = useReveal<HTMLDivElement>()
  return (
    <div
      ref={ref}
      className={`${className} ${inView ? 'animate-fade-in-up' : 'opacity-0'}`}
      style={inView && delay ? { animationDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  )
}

/** Section heading in the reference style: bold black line, optional indigo line. */
function SectionHeading({ title, accent, lead, center = false }: { title: string; accent?: string; lead?: string; center?: boolean }) {
  return (
    <div className={center ? 'text-center max-w-3xl mx-auto' : 'max-w-3xl'}>
      <h2 className="text-3xl md:text-[2.6rem] font-bold tracking-tight leading-[1.12] text-foreground">
        {title}
        {accent && (<><br /><span className="text-indigo-700 dark:text-indigo-400">{accent}</span></>)}
      </h2>
      {lead && <p className="mt-5 text-base md:text-lg text-muted-foreground leading-relaxed">{lead}</p>}
    </div>
  )
}

function Wordmark({ small = false }: { small?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <span className={`${small ? 'w-7 h-7' : 'w-8 h-8'} rounded-lg bg-indigo-600 flex items-center justify-center shadow-sm shadow-indigo-600/30`}>
        <LogoMark className={`${small ? 'w-3.5 h-3.5' : 'w-4 h-4'} text-white`} />
      </span>
      <span className={`${small ? 'text-base' : 'text-lg'} font-bold tracking-tight`}>
        <span className="text-foreground">Tek</span><span className="text-indigo-600 dark:text-indigo-400">Watch</span>
      </span>
    </span>
  )
}

/** Hover or click to open; closes on Escape and when focus leaves the menu. */
function PlatformMenu() {
  const [open, setOpen] = useState(false)
  return (
    <div
      className="relative"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onKeyDown={e => { if (e.key === 'Escape') setOpen(false) }}
      onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setOpen(false) }}
    >
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        aria-haspopup="true"
        className="flex items-center gap-1 hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors"
      >
        Platform <ChevronDown className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute left-1/2 -translate-x-1/2 top-full pt-3 w-80">
          <div className="rounded-xl bg-card p-2 shadow-xl shadow-slate-900/10 ring-1 ring-border">
            {PLATFORM_LINKS.map(l => (
              <a
                key={l.label}
                href={l.href}
                onClick={() => setOpen(false)}
                className="block rounded-lg px-3 py-2.5 hover:bg-indigo-50 dark:hover:bg-indigo-500/15 transition-colors"
              >
                <span className="block text-sm font-semibold text-foreground">{l.label}</span>
                <span className="block text-xs text-muted-foreground mt-0.5">{l.desc}</span>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Diagrams ────────────────────────────────────────────────────────────────

type IconType = typeof Activity

function FlowNode({ x, y, w, title, sub, icon: Icon, accent = false }: {
  x: number; y: number; w: number; title: string; sub: string; icon: IconType; accent?: boolean
}) {
  const h = 56
  return (
    <g>
      {/* Theme colours as classes, so the diagram follows light and dark. */}
      <rect x={x} y={y} width={w} height={h} rx={10} className={accent ? 'fill-card stroke-indigo-400' : 'fill-card stroke-border'} strokeWidth={accent ? 1.5 : 1} />
      <rect x={x + 10} y={y + 12} width={32} height={32} rx={8} className={accent ? 'fill-indigo-600' : 'fill-indigo-50 dark:fill-indigo-500/15'} />
      <Icon x={x + 18} y={y + 20} width={16} height={16} className={accent ? 'text-white' : 'text-indigo-600 dark:text-indigo-300'} strokeWidth={2} />
      <text x={x + 52} y={y + 25} fontSize={12.5} fontWeight={600} className="fill-foreground">{title}</text>
      <text x={x + 52} y={y + 42} fontSize={10.5} className="fill-muted-foreground">{sub}</text>
      <circle cx={x} cy={y + h / 2} r={3.5} className="fill-card stroke-muted-foreground/60" />
      <circle cx={x + w} cy={y + h / 2} r={3.5} className="fill-card stroke-muted-foreground/60" />
    </g>
  )
}

/** How TekWatch actually works, drawn as the pipeline it is. */
function HeroFlow() {
  const outputs = [
    { y: 34,  title: 'Anomaly detection',    sub: '7-day baseline per metric', icon: Activity },
    { y: 146, title: 'Compliance checks',    sub: 'UK GDPR · CE · ISO 27001',  icon: ShieldCheck },
    { y: 258, title: 'Incident correlation', sub: 'Who changed what, when', icon: GitMerge },
  ]
  // Widths leave room for the longest label at the rendered font size.
  const ax = 8, aw = 162, bx = 214, bw = 172, ox = 432, ow = 200, cy = 174
  return (
    <div
      className="relative rounded-2xl border-2 border-border bg-card p-4 shadow-xl shadow-slate-900/5"
      style={{ backgroundImage: 'radial-gradient(hsl(var(--border)) 1px, transparent 1px)', backgroundSize: '16px 16px' }}
    >
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-card/90 px-2 py-1 text-[11px] font-semibold text-muted-foreground ring-1 ring-border">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> Live pipeline
        </span>
        <span className="rounded-md bg-card/90 px-2 py-1 text-[11px] text-muted-foreground ring-1 ring-border">every 15 minutes</span>
      </div>
      <svg viewBox="0 0 640 332" className="w-full h-auto" role="img" aria-label="Your AWS account sends read-only data to the TekWatch agent, which feeds anomaly detection, compliance checks and incident correlation">
        <line x1={ax + aw} y1={cy} x2={bx} y2={cy} stroke="#a5b4fc" strokeWidth={1.5} />
        <line x1={ax + aw} y1={cy} x2={bx} y2={cy} stroke="#4f46e5" strokeWidth={1.5} className="animate-flow" />
        {outputs.map(o => {
          const d = `M${bx + bw} ${cy} C ${bx + bw + 30} ${cy}, ${ox - 30} ${o.y + 28}, ${ox} ${o.y + 28}`
          return (
            <g key={o.title}>
              <path d={d} fill="none" stroke="#a5b4fc" strokeWidth={1.5} />
              <path d={d} fill="none" stroke="#4f46e5" strokeWidth={1.5} className="animate-flow" />
            </g>
          )
        })}
        <FlowNode x={ax} y={cy - 28} w={aw} title="AWS account" sub="EC2 · RDS · S3 · IAM" icon={Cloud} />
        <FlowNode x={bx} y={cy - 28} w={bw} title="TekWatch agent" sub="Read-only, outbound" icon={Radio} accent />
        {outputs.map(o => (
          <FlowNode key={o.title} x={ox} y={o.y} w={ow} title={o.title} sub={o.sub} icon={o.icon} />
        ))}
      </svg>
      <div className="mt-2 flex items-center gap-2 rounded-lg bg-card/95 px-3 py-2 text-xs text-muted-foreground ring-1 ring-border">
        <Mail className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 flex-shrink-0" />
        Anything that needs you arrives by email or Slack, explained in plain English.
      </div>
    </div>
  )
}

/**
 * What the agent reads, and what comes out the other side, animated as the
 * pipeline it is. On first view the boxes and connectors build in order; then
 * data keeps flowing: each service sends a packet to the agent, the agent
 * pulses as they land, and results travel out to each output, which lights up.
 *
 * The flow is SVG (SMIL) animation so every packet, pulse and glow runs on one
 * shared clock and stays in step. It is not rendered for visitors who asked
 * for reduced motion; the entrance is CSS and collapses to its end state
 * under the global reduced-motion rule.
 */
function CoverageDiagram() {
  const top = [
    { x: 85,  title: 'Compute',  sub: 'EC2 · ECS · Lambda' },
    { x: 260, title: 'Data',     sub: 'RDS · S3 · DynamoDB' },
    { x: 435, title: 'Security', sub: 'IAM · GuardDuty · CloudTrail' },
  ]
  const bottom = [
    { x: 85,  title: 'Dashboards', sub: 'Every active region' },
    { x: 260, title: 'Alerts',     sub: 'Email & Slack' },
    { x: 435, title: 'Evidence',   sub: 'Compliance checks' },
  ]
  const [ref, inView] = useReveal<HTMLDivElement>()
  const [flowing, setFlowing] = useState(false)

  useEffect(() => {
    if (!inView) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    // Let the build-in finish before anything moves along the lines.
    const id = setTimeout(() => setFlowing(true), 1600)
    return () => clearTimeout(id)
  }, [inView])

  // Timings in seconds. One cycle: packets leave the three services in turn,
  // reach the agent, then leave the agent for the three outputs.
  const CYCLE = 3.6
  const TRAVEL = 0.32                      // share of the cycle a packet spends moving
  const ARRIVE = TRAVEL * CYCLE            // seconds from leaving to landing
  const IN = top.map((_, i) => 0.2 + i * 0.25)
  const AGENT = IN[0] + ARRIVE
  const OUT = bottom.map((_, i) => IN[2] + ARRIVE + 0.35 + i * 0.2)
  const loop = { dur: `${CYCLE}s`, repeatCount: 'indefinite' as const }
  const delay = (ms: number) => ({ animationDelay: `${ms}ms` })

  const packet = (key: string, path: string, begin: number, tone: 'indigo' | 'emerald') => (
    <g key={key} opacity={0}>
      <circle r={7} className={tone === 'indigo' ? 'fill-indigo-500/20' : 'fill-emerald-500/20'} />
      <circle r={3.2} className={tone === 'indigo' ? 'fill-indigo-500 dark:fill-indigo-300' : 'fill-emerald-500 dark:fill-emerald-300'} />
      <animateMotion path={path} begin={`${begin}s`} {...loop} keyPoints="0;1;1" keyTimes={`0;${TRAVEL};1`} calcMode="linear" />
      <animate attributeName="opacity" values="0;1;1;0;0" keyTimes={`0;0.03;${TRAVEL - 0.03};${TRAVEL};1`} begin={`${begin}s`} {...loop} />
    </g>
  )

  // A ring that flashes once per cycle around a box, starting at `begin`.
  const flash = (key: string, x: number, y: number, begin: number, className: string) => (
    <rect key={key} x={x} y={y} width={162} height={54} rx={11} fill="none" strokeWidth={2} opacity={0} className={className}>
      <animate attributeName="opacity" values="0;0.9;0;0" keyTimes="0;0.06;0.3;1" begin={`${begin}s`} {...loop} />
    </rect>
  )

  const ringTimes = '0;0.05;0.3;1'
  const ringBegin = `${AGENT}s`

  return (
    <div ref={ref}>
      <svg viewBox="0 0 520 262" className="w-full h-auto" role="img" aria-label="Compute, data and security services feed the TekWatch agent, which produces dashboards, alerts and compliance evidence">
        {/* Connectors draw in on first view. */}
        {top.map((t, i) => (
          <line key={t.title} x1={t.x} y1={58} x2={260} y2={106} pathLength={1} strokeWidth={1.2}
            className={`stroke-indigo-400 ${inView ? 'animate-draw' : 'opacity-0'}`} style={delay(380 + i * 90)} />
        ))}
        {bottom.map((b, i) => (
          <line key={b.title} x1={260} y1={156} x2={b.x} y2={204} pathLength={1} strokeWidth={1.2}
            className={`stroke-emerald-400 ${inView ? 'animate-draw' : 'opacity-0'}`} style={delay(980 + i * 90)} />
        ))}

        {/* Packets travel under the boxes, so they vanish into them. */}
        {flowing && top.map((t, i) => packet(`in-${t.title}`, `M${t.x} 58 L260 106`, IN[i], 'indigo'))}
        {flowing && bottom.map((b, i) => packet(`out-${b.title}`, `M260 156 L${b.x} 204`, OUT[i], 'emerald'))}

        {top.map((t, i) => (
          <g key={t.title} className={inView ? 'animate-node-in' : 'opacity-0'} style={delay(i * 110)}>
            <rect x={t.x - 78} y={10} width={156} height={48} rx={8} fill="#312e81" />
            <text x={t.x} y={30} textAnchor="middle" fontSize={12} fontWeight={600} fill="#fbfbfd">{t.title}</text>
            <text x={t.x} y={46} textAnchor="middle" fontSize={9.5} fill="#c7d2fe">{t.sub}</text>
          </g>
        ))}
        {flowing && top.map((t, i) => flash(`send-${t.title}`, t.x - 81, 7, IN[i], 'stroke-indigo-400'))}

        {/* The agent pulses as packets land. */}
        {flowing && (
          <rect x={160} y={106} width={200} height={50} rx={12} fill="none" strokeWidth={1.5} opacity={0} className="stroke-indigo-400">
            <animate attributeName="opacity" values="0;0.8;0;0" keyTimes={ringTimes} begin={ringBegin} {...loop} />
            <animate attributeName="x" values="160;160;150;150" keyTimes={ringTimes} begin={ringBegin} {...loop} />
            <animate attributeName="y" values="106;106;96;96" keyTimes={ringTimes} begin={ringBegin} {...loop} />
            <animate attributeName="width" values="200;200;220;220" keyTimes={ringTimes} begin={ringBegin} {...loop} />
            <animate attributeName="height" values="50;50;70;70" keyTimes={ringTimes} begin={ringBegin} {...loop} />
          </rect>
        )}
        <g className={inView ? 'animate-node-in' : 'opacity-0'} style={delay(700)}>
          <rect x={160} y={106} width={200} height={50} rx={10} className="fill-indigo-50 stroke-indigo-300 dark:fill-indigo-500/15 dark:stroke-indigo-500/50" />
          <text x={260} y={127} textAnchor="middle" fontSize={12.5} fontWeight={700} className="fill-indigo-900 dark:fill-indigo-200">TekWatch agent</text>
          <text x={260} y={144} textAnchor="middle" fontSize={10} className="fill-indigo-600 dark:fill-indigo-300">Read-only · outbound only</text>
        </g>
        {flowing && flash('agent', 157, 104, AGENT, 'stroke-indigo-500')}

        {bottom.map((b, i) => (
          <g key={b.title} className={inView ? 'animate-node-in' : 'opacity-0'} style={delay(1250 + i * 110)}>
            <rect x={b.x - 78} y={204} width={156} height={48} rx={8} className="fill-emerald-50 stroke-emerald-300 dark:fill-emerald-500/10 dark:stroke-emerald-500/40" />
            <text x={b.x} y={224} textAnchor="middle" fontSize={12} fontWeight={600} className="fill-emerald-800 dark:fill-emerald-300">{b.title}</text>
            <text x={b.x} y={240} textAnchor="middle" fontSize={9.5} className="fill-emerald-700 dark:fill-emerald-400">{b.sub}</text>
          </g>
        ))}
        {flowing && bottom.map((b, i) => flash(`land-${b.title}`, b.x - 81, 201, OUT[i] + ARRIVE, 'stroke-emerald-400'))}
      </svg>
    </div>
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  const [billing, setBilling] = useState<'monthly' | 'annual'>('monthly')
  const [activeTab, setActiveTab] = useState<PreviewTabId>('overview')
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const id = setTimeout(() => {
      setActiveTab(prev => {
        const idx = previewTabs.findIndex(t => t.id === prev)
        return previewTabs[(idx + 1) % previewTabs.length].id
      })
    }, 6000)
    return () => clearTimeout(id)
  }, [activeTab])

  const activePath = previewTabs.find(t => t.id === activeTab)?.path ?? '/overview'

  const primaryBtn = 'inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-6 py-3 text-sm font-semibold text-white shadow-sm shadow-indigo-600/25 hover:bg-indigo-700 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2'
  const secondaryBtn = 'inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-card px-6 py-3 text-sm font-semibold text-foreground hover:border-muted-foreground/40 hover:bg-accent transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2'

  return (
    <div className="min-h-screen bg-background text-foreground font-sans antialiased overflow-x-hidden">

      {/* ── Nav ──────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-border bg-background/90 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" aria-label="TekWatch home"><Wordmark /></Link>

          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-foreground/80" aria-label="Main">
            <PlatformMenu />
            <a href="#how-it-works" className="hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors">How it works</a>
            <a href="#pricing" className="hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors">Pricing</a>
            <Link href="/contact" className="hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors">Contact</Link>
          </nav>

          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Link href="/login" className="hidden sm:inline-flex px-3 py-2 text-sm font-semibold text-foreground hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors">
              Sign in
            </Link>
            <Link href="/overview/?demo=1" className="hidden sm:inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 transition-colors">
              Live demo <ArrowRight className="w-3.5 h-3.5" />
            </Link>
            <button
              type="button"
              onClick={() => setMenuOpen(o => !o)}
              aria-expanded={menuOpen}
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              className="md:hidden p-2 -mr-2 text-foreground/80"
            >
              {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {menuOpen && (
          <div className="md:hidden border-t border-border bg-background px-6 py-4 space-y-1">
            {[...PLATFORM_LINKS.slice(0, 3).map(l => ({ label: l.label, href: l.href })),
              { label: 'How it works', href: '#how-it-works' },
              { label: 'Pricing', href: '#pricing' }].map(l => (
              <a key={l.label} href={l.href} onClick={() => setMenuOpen(false)} className="block rounded-lg px-2 py-2.5 text-sm font-medium text-foreground/80 hover:bg-accent">
                {l.label}
              </a>
            ))}
            <Link href="/contact" className="block rounded-lg px-2 py-2.5 text-sm font-medium text-foreground/80 hover:bg-accent">Contact</Link>
            <div className="grid grid-cols-2 gap-2 pt-3">
              <Link href="/login" className={secondaryBtn}>Sign in</Link>
              <Link href="/overview/?demo=1" className={primaryBtn}>Live demo</Link>
            </div>
          </div>
        )}
      </header>

      <main>
      {/* ── Hero ─────────────────────────────────────────── */}
      <section className="px-6 pt-14 pb-20 md:pt-20 md:pb-24">
        <div className="max-w-6xl mx-auto grid lg:grid-cols-[1.02fr_1fr] gap-12 lg:gap-14 items-center">
          <div>
            <p className="animate-fade-in-up inline-flex items-center gap-2 rounded-full border border-indigo-100 dark:border-indigo-500/25 bg-indigo-50 dark:bg-indigo-500/15 px-3 py-1 text-xs font-semibold text-indigo-700 dark:text-indigo-400 mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-600" />
              Cloud monitoring and compliance, built for UK SMEs
            </p>
            <h1
              className="animate-fade-in-up text-[2.4rem] sm:text-5xl lg:text-[3.1rem] font-bold leading-[1.08] tracking-tight text-foreground"
              style={{ animationDelay: '80ms' }}
            >
              Your AWS estate.<br />
              <span className="text-indigo-700 dark:text-indigo-400">Fully visible.<br className="hidden sm:block" /> Risks caught early.</span>
            </h1>
            <p
              className="animate-fade-in-up mt-6 text-base md:text-lg text-muted-foreground leading-relaxed max-w-xl"
              style={{ animationDelay: '160ms' }}
            >
              Know the moment something&apos;s wrong in your AWS estate. TekWatch watches your
              infrastructure around the clock, catching cost spikes, performance issues and
              security risks as they happen, and checking your setup against UK GDPR,
              Cyber Essentials and ISO 27001 from day one.
            </p>
            <div className="animate-fade-in-up mt-8 flex flex-col sm:flex-row gap-3" style={{ animationDelay: '240ms' }}>
              <Link href="/overview/?demo=1" className={primaryBtn}>
                Launch live demo <ArrowRight className="w-4 h-4" />
              </Link>
              <Link href="/signup" className={secondaryBtn}>Start free trial</Link>
            </div>
            <dl className="animate-fade-in-up mt-10 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-2 xl:grid-cols-4 gap-6 border-t border-border pt-6" style={{ animationDelay: '320ms' }}>
              {[
                ['20+', 'AWS services monitored'],
                ['<30 min', 'to first dashboard'],
                ['£79', 'starting price /mo'],
                ['0', 'firewall changes needed'],
              ].map(([val, label]) => (
                <div key={label}>
                  <dt className="sr-only">{label}</dt>
                  <dd className="text-2xl font-bold text-foreground tabular-nums whitespace-nowrap">{val}</dd>
                  <dd className="text-xs text-muted-foreground mt-1 leading-snug">{label}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="animate-fade-in-up hidden sm:block" style={{ animationDelay: '200ms' }}>
            <HeroFlow />
          </div>
        </div>
      </section>

      {/* ── Platform: two engines + product preview ────────── */}
      <section id="platform" className="px-6 py-20 md:py-24 bg-secondary border-y border-border scroll-mt-16">
        <div className="max-w-6xl mx-auto">
          <Reveal>
            <SectionHeading
              title="Monitor, Detect & Prove Compliance"
              lead="One read-only agent feeds detection engines we built ourselves. Every alert, failed check and incident is worked out by TekWatch from your own data, then explained in plain English."
            />
          </Reveal>

          <div className="mt-10 grid md:grid-cols-2 gap-5">
            {[
              {
                icon: Activity,
                title: 'Statistical anomaly detection',
                desc: 'Every metric gets its own 7-day baseline. Readings that break from it become alerts, with the numbers behind them, sent by email or Slack.',
              },
              {
                icon: GitMerge,
                title: 'Incident correlation',
                desc: 'CloudTrail changes are matched to what they did to your resources: who opened a bucket, when, the UK GDPR impact, and the exact commands to fix it.',
              },
            ].map((c, i) => (
              <Reveal key={c.title} delay={i * 80}>
                <div className="h-full flex gap-5 rounded-xl bg-card p-6 ring-1 ring-border shadow-sm">
                  <div className="w-11 h-11 rounded-lg bg-indigo-50 dark:bg-indigo-500/15 flex items-center justify-center flex-shrink-0">
                    <c.icon className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-foreground">{c.title}</h3>
                    <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{c.desc}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>

          {/* Product preview: a dark screenshot of the real app */}
          <Reveal className="mt-10">
            <div className="dark rounded-2xl ring-1 ring-border shadow-2xl shadow-slate-900/20 overflow-hidden">
              <div className="bg-card text-foreground">
                {/* Fake browser tab strip, doubles as the view switcher */}
                <div className="flex items-center gap-1 px-3 pt-3 bg-black/20 border-b border-border overflow-x-auto">
                  {previewTabs.map(tab => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      aria-current={activeTab === tab.id ? 'true' : undefined}
                      className={`flex-shrink-0 px-3.5 py-2 rounded-t-md text-xs font-medium transition-colors ${
                        activeTab === tab.id
                          ? 'bg-card text-foreground border border-b-0 border-border'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                {/* Mock browser chrome */}
                <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-black/20">
                  <div className="w-3 h-3 rounded-full bg-red-400/70" />
                  <div className="w-3 h-3 rounded-full bg-amber-400/70" />
                  <div className="w-3 h-3 rounded-full bg-emerald-400/70" />
                  <div className="flex-1 mx-4 min-w-0">
                    <div className="h-5 rounded-md bg-background border border-border max-w-72 mx-auto flex items-center justify-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      <span className="text-xs text-muted-foreground font-mono truncate">app.tekwatch.io{activePath}</span>
                    </div>
                  </div>
                </div>

                {/* Mock dashboard */}
                <div key={activeTab} className="p-5 space-y-3 animate-fade-in">
                {activeTab === 'overview' && (<>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {statTiles.map(s => (
                      <div key={s.label} className="rounded-xl border border-border bg-background/60 p-4 flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-2">
                            <s.icon className="w-3.5 h-3.5" />
                            {s.label}
                          </div>
                          <div className="font-mono text-2xl font-semibold text-foreground mb-1.5">{s.value}</div>
                          <div className={`flex items-center gap-1 text-xs font-medium ${s.good ? 'text-emerald-400' : 'text-amber-400'}`}>
                            {s.good ? <TrendingDown className="w-3 h-3" /> : <TrendingUp className="w-3 h-3" />}
                            {s.delta} <span className="text-muted-foreground font-normal">{s.sub}</span>
                          </div>
                        </div>
                        <Sparkline data={s.trend} color={s.good ? '#34d399' : '#fbbf24'} />
                      </div>
                    ))}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div className="md:col-span-2 min-w-0 rounded-xl border border-border bg-background/60 p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-xs text-muted-foreground">Daily AWS Spend (Last 30 Days)</div>
                        <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                          <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-[2px] rounded-full bg-indigo-400" />This month</span>
                          <span className="flex items-center gap-1.5"><span className="inline-block w-3 border-t-2 border-dashed border-slate-500" />Last month</span>
                        </div>
                      </div>
                      <div aria-hidden="true"><ResponsiveContainer width="100%" height={170}>
                        <AreaChart data={spendData} margin={{ top: 14, right: 60, left: 0, bottom: 0 }}>
                          <defs>
                            <linearGradient id="spendFill" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#818cf8" stopOpacity={0.2} />
                              <stop offset="60%" stopColor="#818cf8" stopOpacity={0.04} />
                              <stop offset="100%" stopColor="#818cf8" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.06)" />
                          <XAxis dataKey="day" hide />
                          <YAxis hide domain={[0, 'dataMax + 20']} />
                          <Tooltip
                            contentStyle={TIP_STY}
                            labelFormatter={d => `Day ${d}`}
                            formatter={(v: number, name: string) => [`£${v}`, name === 'spend' ? 'This month' : 'Last month']}
                            cursor={{ stroke: 'rgba(255,255,255,0.15)', strokeWidth: 1 }}
                          />
                          <ReferenceLine y={avgSpend} stroke="rgba(255,255,255,0.18)" strokeDasharray="3 3" />
                          <Area type="monotone" dataKey="prevSpend" stroke="#64748b" strokeWidth={1.5} strokeDasharray="4 3"
                            fill="none" dot={false} activeDot={{ r: 3, fill: '#64748b', stroke: '#0e1525', strokeWidth: 1.5 }} />
                          <Area type="monotone" dataKey="spend" stroke="#818cf8" strokeWidth={2}
                            fill="url(#spendFill)" dot={false}
                            activeDot={{ r: 4, fill: '#818cf8', stroke: '#0e1525', strokeWidth: 2 }} />
                          <ReferenceDot
                            x={anomalyPoint.day} y={anomalyPoint.spend} r={5}
                            fill="#fbbf24" stroke="#0e1525" strokeWidth={2}
                            label={{ value: 'Flagged', position: 'top', fill: '#fbbf24', fontSize: 10, fontWeight: 600 }}
                          />
                        </AreaChart>
                      </ResponsiveContainer></div>
                    </div>

                    <div className="rounded-xl border border-border bg-background/60 p-4 flex flex-col">
                      <div className="text-xs text-muted-foreground mb-1">Compliance checks</div>
                      <div className="relative w-full h-[104px] flex-shrink-0">
                        <div aria-hidden="true"><ResponsiveContainer width="100%" height={104}>
                          <RadialBarChart innerRadius="70%" outerRadius="92%" data={scoreData} startAngle={90} endAngle={-270}>
                            <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                            <RadialBar dataKey="value" cornerRadius={6} background={{ fill: 'rgba(255,255,255,0.08)' }} />
                          </RadialBarChart>
                        </ResponsiveContainer></div>
                        <div className="absolute inset-0 flex flex-col items-center justify-center">
                          <span className="font-mono text-2xl font-semibold text-foreground">91%</span>
                        </div>
                      </div>
                      <div className="mt-2 pt-2 border-t border-white/5 space-y-1.5">
                        {complianceFrameworks.map(f => (
                          <div key={f.label} className="flex items-center justify-between text-[11px]">
                            <span className="text-muted-foreground">{f.label}</span>
                            <span className={`flex items-center gap-1 font-medium ${f.status === 'pass' ? 'text-emerald-400' : 'text-amber-400'}`}>
                              <span className={`w-1.5 h-1.5 rounded-full ${f.status === 'pass' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                              {f.status === 'pass' ? 'Pass' : '2 findings'}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="rounded-xl border border-border bg-background/60 p-4">
                    <div className="text-xs text-muted-foreground mb-2">Top AWS Services by Cost (This Month)</div>
                    <div aria-hidden="true"><ResponsiveContainer width="100%" height={150}>
                      <BarChart data={serviceCostData} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                        <CartesianGrid horizontal={false} vertical={false} />
                        <XAxis type="number" hide />
                        <YAxis type="category" dataKey="service" tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} width={76} />
                        <Tooltip contentStyle={TIP_STY} formatter={(v: number) => [`£${v}`, 'Cost']} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                        <Bar dataKey="cost" radius={[0, 4, 4, 0]} barSize={14}>
                          {serviceCostData.map((d, i) => (
                            <Cell key={i} fill={d.cost === maxServiceCost ? '#fbbf24' : '#818cf8'} fillOpacity={d.cost === maxServiceCost ? 1 : 0.7} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer></div>
                  </div>

                  <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-3 flex items-center gap-3">
                    <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
                    <div className="text-xs text-red-400 font-semibold tracking-wide">CRITICAL</div>
                    <div className="text-xs text-foreground/80 flex-1">CPU utilisation on web-server-01 is 92.4% (threshold: 80%)</div>
                    <div className="text-xs text-muted-foreground">15m ago</div>
                  </div>
                </>)}

                {activeTab === 'security' && (<>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {securitySummaryTiles.map(s => (
                      <div key={s.label} className="rounded-xl border border-border bg-background/60 p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs text-muted-foreground">{s.label}</span>
                          <div className={`w-6 h-6 rounded-md border flex items-center justify-center ${s.bg}`}>
                            <s.icon className={`w-3.5 h-3.5 ${s.tone}`} />
                          </div>
                        </div>
                        <div className={`font-mono text-2xl font-semibold ${s.tone}`}>{s.value}</div>
                      </div>
                    ))}
                  </div>

                  <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-4">
                    <div className="text-xs text-muted-foreground mb-3">Compliance checks (3 frameworks)</div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-6 gap-y-3">
                      {compliancePreview.map(c => (
                        <div key={c.label}>
                          <div className="flex items-center justify-between mb-1.5 text-xs">
                            <span className="text-foreground/80">{c.label}</span>
                            <span className="font-mono font-semibold text-foreground">{c.score}%</span>
                          </div>
                          <div className="h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${c.score >= 90 ? 'bg-emerald-400' : c.score >= 75 ? 'bg-amber-400' : 'bg-red-400'}`}
                              style={{ width: `${c.score}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-xl border border-border bg-background/60 p-4">
                    <div className="text-xs text-muted-foreground mb-3">GuardDuty Findings</div>
                    <div className="space-y-2">
                      {guardDutyPreview.map(f => (
                        <div key={f.title} className="flex items-center gap-3 rounded-lg border border-border bg-background/40 px-3 py-2.5">
                          <span className={`flex-shrink-0 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold ${
                            f.severity === 'MEDIUM' ? 'text-amber-400 bg-amber-500/10 border border-amber-500/20' : 'text-muted-foreground bg-white/5 border border-white/10'
                          }`}>{f.severity}</span>
                          <span className="text-xs text-foreground/80 flex-1 truncate">{f.title}</span>
                          <span className="text-[11px] text-muted-foreground hidden sm:inline">{f.resource}</span>
                          <span className="text-[11px] text-muted-foreground flex-shrink-0">{f.age}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </>)}

                {activeTab === 'cost' && (<>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="rounded-xl border border-border bg-background/60 p-4">
                      <div className="text-xs text-muted-foreground mb-3">MTD Spend by Service</div>
                      <div className="flex items-center gap-5">
                        <svg width={156} height={156} viewBox="0 0 156 156" className="flex-shrink-0" aria-hidden="true">
                          {donutSegments.map(s => (
                            <circle
                              key={s.color}
                              cx={DONUT_CX} cy={DONUT_CY} r={DONUT_R}
                              fill="none" stroke={s.color} strokeWidth={18}
                              strokeDasharray={`${s.frac * donutCirc} ${donutCirc}`}
                              strokeDashoffset={-s.offset * donutCirc}
                              transform={`rotate(-90 ${DONUT_CX} ${DONUT_CY})`}
                            />
                          ))}
                          <text x={DONUT_CX} y={DONUT_CY - 4} textAnchor="middle" fill="#e2eaf4" fontSize={16} fontFamily="var(--font-mono)" fontWeight="600">
                            £{donutTotal.toLocaleString('en-GB')}
                          </text>
                          <text x={DONUT_CX} y={DONUT_CY + 14} textAnchor="middle" fill="#64748b" fontSize={9}>MTD total</text>
                        </svg>
                        <div className="space-y-1.5 flex-1 min-w-0">
                          {serviceCostData.map((d, i) => (
                            <div key={d.service} className="flex items-center gap-2">
                              <span className="w-2 h-2 rounded-sm flex-shrink-0" style={{ background: SERVICE_COLORS[i % SERVICE_COLORS.length] }} />
                              <span className="text-xs text-muted-foreground truncate flex-1">{d.service}</span>
                              <span className="text-xs font-mono text-foreground">£{d.cost}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="rounded-xl border border-border bg-background/60 p-4 flex flex-col justify-between">
                      <div>
                        <div className="text-xs text-muted-foreground mb-2">Month-End Forecast</div>
                        <div className="font-mono text-3xl font-semibold text-foreground mb-1.5">£2,140</div>
                        <div className="flex items-center gap-1 text-xs font-medium text-amber-400">
                          <TrendingUp className="w-3 h-3" /> +8% <span className="text-muted-foreground font-normal">vs last month</span>
                        </div>
                      </div>
                      <div className="mt-4 flex items-start gap-2 rounded-lg border border-indigo-500/20 bg-indigo-500/5 p-2.5">
                        <Sparkles className="w-3.5 h-3.5 text-indigo-300 flex-shrink-0 mt-0.5" />
                        <span className="text-[11px] text-foreground/80 leading-relaxed">
                          2 cost spikes flagged this month. The largest: an idle RDS instance running 24/7 in eu-west-1.
                        </span>
                      </div>
                    </div>
                  </div>
                </>)}

                {activeTab === 'assistant' && (<>
                  <div className="rounded-xl border border-border bg-background/60 p-4 space-y-4">
                    <div className="flex justify-end">
                      <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-indigo-600 text-white text-sm px-4 py-2.5">
                        {chatExchange.question}
                      </div>
                    </div>
                    <div className="flex items-start gap-2.5">
                      <div className="w-7 h-7 rounded-full bg-white/5 border border-border flex items-center justify-center flex-shrink-0">
                        <Bot className="w-3.5 h-3.5 text-indigo-300" />
                      </div>
                      <div className="space-y-2 flex-1">
                        <div className="rounded-2xl rounded-tl-sm bg-background border border-border text-foreground/90 text-sm leading-relaxed px-4 py-3">
                          {chatExchange.answer}
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {chatExchange.tools.map(t => (
                            <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-500/10 border border-indigo-500/20 text-indigo-200">
                              <Sparkles className="w-2.5 h-2.5" />
                              {t}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="rounded-xl border border-border bg-background/60 p-3 flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="flex-1">Ask about cost, security, or anything in your AWS estate...</span>
                    <span className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center flex-shrink-0">
                      <ArrowRight className="w-3 h-3 text-white" />
                    </span>
                  </div>
                </>)}
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ── The Problem ──────────────────────────────────── */}
      <section className="px-6 py-20 md:py-24">
        <div className="max-w-6xl mx-auto">
          <Reveal>
            <SectionHeading
              title="Monitoring is priced for enterprises."
              accent="Most UK SMEs go without."
              lead="Enterprise tools like Datadog cost £800–£5,000/month and need a specialist to run. For 5.5 million UK SMEs, that’s not a pricing tier. It’s a locked door."
            />
          </Reveal>
          <div className="mt-10 grid grid-cols-2 lg:grid-cols-4 gap-4">
            {problemStats.map((s, i) => (
              <Reveal key={s.label} delay={i * 60}>
                <div className="h-full rounded-xl bg-card p-5 ring-1 ring-border shadow-sm">
                  <s.icon className="w-5 h-5 text-indigo-600 dark:text-indigo-400 mb-4" />
                  <div className="text-3xl font-bold text-foreground tabular-nums">{s.value}</div>
                  <p className="mt-2 text-sm text-muted-foreground leading-snug">{s.label}</p>
                  <p className="mt-3 text-[11px] text-muted-foreground/70">{s.source}</p>
                </div>
              </Reveal>
            ))}
          </div>
          <Reveal className="mt-8">
            <p className="rounded-xl border-l-4 border-indigo-600 bg-indigo-50/60 dark:bg-indigo-500/10 px-6 py-5 text-base md:text-lg font-medium text-foreground/90">
              Built by engineers who monitor AWS for a living. Made for the businesses who don&apos;t have one on staff.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ── Capabilities (top-border cards) ──────────────── */}
      <section id="capabilities" className="px-6 py-20 md:py-24 bg-secondary border-y border-border scroll-mt-16">
        <div className="max-w-6xl mx-auto">
          <Reveal>
            <SectionHeading
              title="Everything your team needs"
              lead="From real-time resource health to UK-specific compliance evidence, all in one place."
            />
          </Reveal>
          <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {FEATURES.map((f, i) => (
              <Reveal key={f.title} delay={(i % 3) * 70}>
                <div className="group h-full rounded-xl border-t-4 border-t-indigo-600 bg-card p-6 ring-1 ring-border shadow-sm transition-shadow hover:shadow-lg hover:shadow-slate-900/5">
                  <div className="flex items-center gap-3">
                    <f.icon className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                    <h3 className="text-lg font-semibold text-foreground">{f.title}</h3>
                  </div>
                  <p className="mt-3 text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
                  <ul className="mt-4 space-y-1.5">
                    {f.points.map(p => (
                      <li key={p} className="flex items-center gap-2 text-sm text-foreground/80">
                        <Check className="w-4 h-4 text-indigo-600 dark:text-indigo-400 flex-shrink-0" />
                        {p}
                      </li>
                    ))}
                  </ul>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Deploy faster: checklist + coverage diagram ──── */}
      <section className="px-6 py-20 md:py-24">
        <div className="max-w-6xl mx-auto">
          <Reveal>
            <SectionHeading
              title="Connected in 30 Minutes. No Firewall Changes."
              lead="The agent runs as one ECS Fargate task inside your own AWS account, with a read-only IAM role, and only ever sends data out. Nothing to open, nothing to install on your servers."
            />
          </Reveal>
          <div className="mt-10 grid lg:grid-cols-2 gap-10 items-center">
            <Reveal>
              <ul className="space-y-4">
                {[
                  'Read-only IAM role, created for you by CloudFormation',
                  'Outbound only: no inbound ports, no VPN, no firewall rules',
                  '20+ AWS services across every active region',
                  'Your data stays in the UK (AWS London, eu-west-2)',
                ].map(p => (
                  <li key={p} className="flex items-start gap-3 text-base text-foreground/80">
                    <span className="mt-0.5 w-5 h-5 rounded-full bg-indigo-50 dark:bg-indigo-500/15 flex items-center justify-center flex-shrink-0">
                      <Check className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                    </span>
                    {p}
                  </li>
                ))}
              </ul>
              <Link href="/signup" className="mt-8 inline-flex items-center gap-1.5 text-sm font-semibold text-indigo-700 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-200">
                Connect your AWS account <ChevronRight className="w-4 h-4" />
              </Link>
            </Reveal>
            <Reveal delay={100}>
              <div className="rounded-2xl bg-card p-5 ring-1 ring-border shadow-sm">
                <CoverageDiagram />
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ── How it works (left-border cards) ─────────────── */}
      <section id="how-it-works" className="px-6 py-20 md:py-24 bg-secondary border-y border-border scroll-mt-16">
        <div className="max-w-6xl mx-auto">
          <Reveal>
            <SectionHeading
              title="Stop Guessing About Your AWS,"
              accent="Start Seeing It"
              lead="No sales call. No credit card. No specialist knowledge required."
            />
          </Reveal>
          <div className="mt-10 grid md:grid-cols-3 gap-5">
            {ONBOARDING_STEPS.map((s, i) => (
              <Reveal key={s.title} delay={i * 80}>
                <div className="h-full rounded-xl border-l-4 border-indigo-600 bg-card p-6 ring-1 ring-border shadow-sm">
                  <span className="text-xs font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">Step {i + 1}</span>
                  <h3 className="mt-2 text-lg font-semibold text-foreground">{s.title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{s.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pricing ──────────────────────────────────────── */}
      <section id="pricing" className="px-6 py-20 md:py-24 scroll-mt-16">
        <div className="max-w-5xl mx-auto">
          <Reveal>
            <SectionHeading
              center
              title="Simple, predictable pricing"
              lead="Self-service SaaS. No implementation fees, no sales call required."
            />
          </Reveal>

          <div className="mt-8 flex justify-center">
            <div className="inline-flex items-center gap-1 rounded-lg bg-muted p-1">
              <button
                onClick={() => setBilling('monthly')}
                className={`px-4 py-2 rounded-md text-sm font-semibold transition-colors ${billing === 'monthly' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
              >
                Monthly
              </button>
              <button
                onClick={() => setBilling('annual')}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-semibold transition-colors ${billing === 'annual' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
              >
                Annual
                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400">Save up to 15%</span>
              </button>
            </div>
          </div>

          <div className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-5">
            {pricingTiers.map(p => {
              const displayPrice = billing === 'annual' ? Math.round(p.monthly * (1 - p.discount)) : p.monthly
              return (
                <div
                  key={p.name}
                  className={`relative flex flex-col rounded-xl bg-card p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-lg ${
                    p.highlight ? 'ring-2 ring-indigo-600' : 'ring-1 ring-border'
                  }`}
                >
                  {p.highlight && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-600 text-white shadow-sm">
                      Most popular
                    </div>
                  )}
                  <h3 className="text-lg font-semibold text-foreground">{p.name}</h3>
                  <div className="mt-2 flex items-baseline gap-1">
                    <span className="text-4xl font-bold text-foreground tabular-nums">£{displayPrice}</span>
                    <span className="text-sm text-muted-foreground">/month</span>
                  </div>
                  <div className="h-5 mt-1">
                    {billing === 'annual' && (
                      <span className="text-xs text-emerald-700 dark:text-emerald-400">Billed annually · save {Math.round(p.discount * 100)}%</span>
                    )}
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">{p.desc}</p>
                  <ul className="mt-5 mb-6 space-y-2 flex-1">
                    {p.features.map(f => (
                      <li key={f} className="flex items-start gap-2 text-sm text-foreground/80">
                        <Check className="w-4 h-4 mt-0.5 text-indigo-600 dark:text-indigo-400 flex-shrink-0" />
                        {f}
                      </li>
                    ))}
                  </ul>
                  <Link href="/signup" className={p.highlight ? primaryBtn : secondaryBtn}>
                    Start free trial
                  </Link>
                </div>
              )
            })}
          </div>
          <p className="text-center text-sm text-muted-foreground mt-8">
            Want it fully managed? Tek Tribe&apos;s Managed Cloud Services start from{' '}
            <span className="font-semibold text-foreground">£500/month</span>, TekWatch included.
          </p>
        </div>
      </section>

      {/* ── Get started ──────────────────────────────────── */}
      <section className="px-6 py-20 md:py-24 bg-secondary border-t border-border">
        <div className="max-w-6xl mx-auto">
          <Reveal>
            <div className="text-center max-w-3xl mx-auto">
              <p className="text-sm font-bold uppercase tracking-[0.18em] text-indigo-600 dark:text-indigo-400">Get started</p>
              <h2 className="mt-3 text-3xl md:text-[2.6rem] font-bold tracking-tight leading-[1.12] text-foreground">
                See your AWS estate clearly,<br className="hidden sm:block" /> starting today
              </h2>
              <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
                <Link href="/overview/?demo=1" className={primaryBtn}>Launch live demo <ArrowRight className="w-4 h-4" /></Link>
                <Link href="/signup" className={secondaryBtn}>Start free trial</Link>
              </div>
            </div>
          </Reveal>

          <div className="mt-14 grid md:grid-cols-3 gap-5">
            {[
              { icon: MessageSquare, title: 'Ready to get started?', desc: 'Talk to the team about your AWS estate and what you need to prove.', cta: 'Contact us', href: '/contact' },
              { icon: Mail, title: 'Questions?', desc: 'Setup, billing or compliance, email us and an engineer will get back to you.', cta: 'hello@tekwatch.io', href: 'mailto:hello@tekwatch.io' },
              { icon: Sparkles, title: 'Live demo', desc: 'Explore a fully populated sample dashboard. No account needed.', cta: 'Explore now', href: '/overview/?demo=1' },
            ].map((c, i) => (
              <Reveal key={c.title} delay={i * 70}>
                <div className="h-full flex flex-col rounded-xl bg-card p-6 ring-1 ring-border shadow-sm">
                  <c.icon className="w-7 h-7 text-indigo-600 dark:text-indigo-400" strokeWidth={1.6} />
                  <h3 className="mt-5 text-xl font-bold text-foreground">{c.title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground leading-relaxed flex-1">{c.desc}</p>
                  {c.href.startsWith('mailto:') ? (
                    <a href={c.href} className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-indigo-700 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-200">
                      {c.cta} <ChevronRight className="w-4 h-4" />
                    </a>
                  ) : (
                    <Link href={c.href} className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-indigo-700 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-200">
                      {c.cta} <ChevronRight className="w-4 h-4" />
                    </Link>
                  )}
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>
      </main>

      {/* ── Footer ───────────────────────────────────────── */}
      <footer className="bg-background px-6 pt-16 pb-8 border-t border-border">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-10 mb-12">
            <div className="col-span-2 md:col-span-1">
              <Wordmark small />
              <p className="mt-5 text-2xl font-bold leading-snug text-muted-foreground/70">See TekWatch<br />in action</p>
              <Link href="/overview/?demo=1" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-indigo-700 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-200">
                Launch live demo <ChevronRight className="w-4 h-4" />
              </Link>
              <div className="mt-6 flex items-center gap-3">
                <a href="#" aria-label="TekWatch on LinkedIn" className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-200 transition-colors">
                  <Linkedin className="w-4 h-4" />
                </a>
                <a href="#" aria-label="Tek Talk on YouTube" className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-200 transition-colors">
                  <Youtube className="w-4 h-4" />
                </a>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-bold text-foreground mb-4">Product</h3>
              <ul className="space-y-3 text-sm text-muted-foreground">
                <li><a href="#platform" className="hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors">Platform</a></li>
                <li><a href="#capabilities" className="hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors">Capabilities</a></li>
                <li><a href="#pricing" className="hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors">Pricing</a></li>
                <li><Link href="/overview/?demo=1" className="hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors">Live demo</Link></li>
              </ul>
            </div>

            <div>
              <h3 className="text-sm font-bold text-foreground mb-4">Company</h3>
              <ul className="space-y-3 text-sm text-muted-foreground">
                <li><Link href="/signup" className="hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors">Sign up</Link></li>
                <li><Link href="/login" className="hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors">Sign in</Link></li>
                <li><Link href="/contact" className="hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors">Contact us</Link></li>
              </ul>
            </div>

            <div>
              <h3 className="text-sm font-bold text-foreground mb-4">Contact</h3>
              <ul className="space-y-3 text-sm text-muted-foreground">
                <li className="flex items-center gap-2">
                  <Mail className="w-3.5 h-3.5 flex-shrink-0 text-indigo-600 dark:text-indigo-400" />
                  <a href="mailto:hello@tekwatch.io" className="hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors">hello@tekwatch.io</a>
                </li>
                <li className="flex items-center gap-2">
                  <MapPin className="w-3.5 h-3.5 flex-shrink-0 text-indigo-600 dark:text-indigo-400" />
                  Glasgow, Scotland, UK
                </li>
              </ul>
            </div>
          </div>

          <div className="pt-8 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-muted-foreground">
            <p>© 2026 Tek Tribe Ltd. All rights reserved.</p>
            <p>AWS monitoring and UK compliance checks, built for SMEs.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}

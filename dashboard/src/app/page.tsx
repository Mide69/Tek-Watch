'use client'

import { useState, useId, useEffect, useRef } from 'react'
import Link from 'next/link'
import {
  Radio, Activity, Shield, DollarSign, Zap, Server, Cpu, AlertTriangle,
  TrendingUp, TrendingDown, Award, BadgeCheck, ShieldCheck,
  ArrowRight, Check, Gavel, PoundSterling, BarChart3,
  Linkedin, Youtube, Mail, MapPin, Bot, Sparkles, Key, Users,
} from 'lucide-react'
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  RadialBarChart, RadialBar, PolarAngleAxis, ReferenceDot, ReferenceLine,
  BarChart, Bar, Cell,
} from 'recharts'

const TIP_STY = { borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)', background: '#0e1525', fontSize: 12, color: '#e2eaf4' }

const spendCurrent = [45, 52, 48, 61, 58, 70, 65, 72, 68, 75, 80, 73, 69, 78, 82, 88, 77, 74, 83, 91, 86, 79, 88, 95, 92, 88, 97, 105, 99, 112]
const spendPrevious = [40, 44, 43, 52, 50, 58, 56, 60, 59, 63, 66, 62, 60, 65, 68, 71, 66, 65, 69, 74, 71, 68, 73, 76, 75, 73, 77, 80, 78, 79]
const spendData = spendCurrent.map((v, i) => ({ day: i + 1, spend: v, prevSpend: spendPrevious[i] }))
const avgSpend = Math.round(spendCurrent.reduce((s, v) => s + v, 0) / spendCurrent.length)
const anomalyPoint = spendData[spendData.length - 1]

const scoreData = [{ name: 'score', value: 91, fill: '#818cf8' }]

const complianceFrameworks = [
  { label: 'UK GDPR', status: 'pass' as const },
  { label: 'Cyber Essentials Plus', status: 'pass' as const },
  { label: 'FCA PS21/3', status: 'pending' as const },
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

const SERVICE_COLORS = ['#818cf8', '#22d3ee', '#fbbf24', '#34d399', '#f97316', '#a78bfa']
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
  { label: 'UK GDPR', score: 96 },
  { label: 'Cyber Essentials Plus', score: 91 },
  { label: 'FCA PS21/3', score: 78 },
  { label: 'ISO 27001', score: 88 },
]

const securitySummaryTiles = [
  { icon: AlertTriangle, label: 'GuardDuty Findings', value: '2', tone: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20' },
  { icon: Users, label: 'Users w/o MFA', value: '1', tone: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' },
  { icon: Key, label: 'Old Access Keys', value: '3', tone: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' },
  { icon: ShieldCheck, label: 'Certs Expiring <30d', value: '0', tone: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' },
]

const chatExchange = {
  question: 'Why did my AWS bill spike this week?',
  answer: 'Your spend jumped 18% on Tuesday — mostly EC2. Three on-demand instances in eu-west-2 have run at steady utilisation for 30 days straight; switching them to Reserved would save roughly £140/month.',
  tools: ['Cost breakdown', 'EC2 instances'],
}

const previewTabs = [
  { id: 'overview', label: 'Overview', path: '/overview' },
  { id: 'security', label: 'Security', path: '/security' },
  { id: 'cost', label: 'Cost', path: '/cost' },
  { id: 'assistant', label: 'AI Assistant', path: '/chat' },
] as const

type PreviewTabId = typeof previewTabs[number]['id']

const FEATURES = [
  {
    icon: Activity, color: 'text-indigo-600 dark:text-indigo-400',
    bg: 'bg-indigo-500/8 dark:bg-indigo-500/10', border: 'border-indigo-500/20',
    title: 'Real-time Visibility',
    desc: 'EC2, RDS, Lambda, ECS/EKS, S3, DynamoDB and 14 more AWS services — full visibility across every active region from your first dashboard load.',
    points: ['20+ AWS services monitored', 'Every active region, day one', '90-day metric history'],
  },
  {
    icon: Zap, color: 'text-violet-600 dark:text-violet-400',
    bg: 'bg-violet-500/8 dark:bg-violet-500/10', border: 'border-violet-500/20',
    title: 'AI Anomaly Detection',
    desc: "TekWatch's proprietary AI engine learns your normal baseline and flags genuine anomalies — no manual thresholds, no specialist configuration required.",
    points: ['Zero-configuration, self-learning', 'Cost, performance & security', 'Plain-English explanations'],
  },
  {
    icon: Shield, color: 'text-cyan-600 dark:text-cyan-400',
    bg: 'bg-cyan-500/8 dark:bg-cyan-500/10', border: 'border-cyan-500/20',
    title: 'UK Compliance Intelligence',
    desc: 'Built-in mapping to the UK regulatory frameworks SMEs actually face — automated evidence, not a generic US compliance checklist.',
    points: ['UK GDPR & Cyber Essentials Plus', 'FCA PS21/3 resilience module', 'GuardDuty & Security Hub findings'],
  },
  {
    icon: DollarSign, color: 'text-emerald-600 dark:text-emerald-400',
    bg: 'bg-emerald-500/8 dark:bg-emerald-500/10', border: 'border-emerald-500/20',
    title: 'Cost Intelligence',
    desc: 'MTD spend, 30-day trends, per-service breakdowns, and AI-flagged cost anomalies before the bill arrives.',
    points: ['Daily spend trends', 'Per-service breakdown', 'AI cost anomaly alerts'],
  },
  {
    icon: Server, color: 'text-amber-600 dark:text-amber-400',
    bg: 'bg-amber-500/8 dark:bg-amber-500/10', border: 'border-amber-500/20',
    title: 'Managed Service Option',
    desc: "Don't want to DIY? Tek Tribe's own engineers monitor and manage it for you — from £500/month, with TekWatch included.",
    points: ['Continuous monitoring & patching', 'Compliance reporting included', '20–30% typical cost savings'],
  },
  {
    icon: Radio, color: 'text-rose-600 dark:text-rose-400',
    bg: 'bg-rose-500/8 dark:bg-rose-500/10', border: 'border-rose-500/20',
    title: 'Lightweight Agent',
    desc: 'A single ECS Fargate task in your AWS account. Read-only IAM, outbound-only, zero firewall changes.',
    points: ['ECS Fargate', 'Read-only IAM role', 'Auto-deploy CloudFormation'],
  },
]

const ONBOARDING_STEPS = [
  {
    title: 'Start your free trial',
    desc: 'Create an account at tekwatch.co.uk. 14 days free, no credit card required — you can be looking at your own data within minutes.',
  },
  {
    title: 'Deploy in under 30 minutes',
    desc: 'Download your pre-configured CloudFormation template and deploy the read-only monitoring agent. No inbound firewall changes needed.',
  },
  {
    title: 'See what’s really going on',
    desc: 'Your dashboard populates with live infrastructure data immediately — anomalies, compliance gaps and cost overruns, explained in plain English.',
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
    features: ['Up to 2 AWS accounts', '50 monitored resources', 'AI anomaly detection', 'UK GDPR compliance module'],
    highlight: false,
  },
  {
    name: 'Business', monthly: 199, discount: 0.10,
    desc: 'For growing SMEs, FinTech firms and professional services.',
    features: ['Up to 5 AWS accounts', '500 monitored resources', 'Full AI engine + cost anomaly detection', 'UK GDPR + Cyber Essentials Plus', 'Slack & Microsoft Teams alerts'],
    highlight: true,
  },
  {
    name: 'Enterprise', monthly: 499, discount: 0.15,
    desc: 'For mid-market and regulated businesses with complex environments.',
    features: ['Unlimited accounts & resources', 'All five UK compliance frameworks', 'Full API access', 'Dedicated 2-hour support'],
    highlight: false,
  },
]

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
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true)
          observer.disconnect()
        }
      },
      { threshold: 0.2 }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  return [ref, inView] as const
}

interface Feature {
  icon: typeof Activity
  color: string
  bg: string
  border: string
  title: string
  desc: string
  points: string[]
}

function FeatureCard({ f, index, inView }: { f: Feature; index: number; inView: boolean }) {
  const [spot, setSpot] = useState({ x: 50, y: 0 })

  return (
    <div
      onMouseMove={e => {
        const rect = e.currentTarget.getBoundingClientRect()
        setSpot({ x: ((e.clientX - rect.left) / rect.width) * 100, y: ((e.clientY - rect.top) / rect.height) * 100 })
      }}
      className="group relative overflow-hidden rounded-lg border border-white/10 bg-white/[0.03] hover:border-white/20 p-5 transition-[transform,border-color] duration-500 hover:-translate-y-1"
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? undefined : 'translateY(16px)',
        transition: `opacity 0.6s ease-out ${index * 90}ms, transform 0.6s cubic-bezier(0.16,1,0.3,1) ${index * 90}ms, border-color 0.3s, translate 0.5s`,
      }}
    >
      {/* Cursor-tracked spotlight */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
        style={{ background: `radial-gradient(280px circle at ${spot.x}% ${spot.y}%, rgba(129,140,248,0.12), transparent 70%)` }}
      />
      <div className="relative">
        <div className={`w-10 h-10 rounded-lg ${f.bg} border ${f.border} flex items-center justify-center mb-4 transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-3`}>
          <f.icon className={`w-5 h-5 ${f.color}`} />
        </div>
        <h3 className="font-semibold text-foreground mb-2">{f.title}</h3>
        <p className="text-sm text-muted-foreground mb-4 leading-relaxed">{f.desc}</p>
        <ul className="space-y-1.5">
          {f.points.map(p => (
            <li key={p} className="flex items-center gap-2 text-xs text-muted-foreground">
              <Check className={`w-3.5 h-3.5 ${f.color} flex-shrink-0`} />
              {p}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export default function LandingPage() {
  const [billing, setBilling] = useState<'monthly' | 'annual'>('monthly')
  const [activeTab, setActiveTab] = useState<PreviewTabId>('overview')

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
  const [featuresRef, featuresInView] = useReveal<HTMLDivElement>()

  return (
    <div className="dark min-h-screen bg-background text-foreground overflow-x-hidden">

      {/* ── Nav ──────────────────────────────────────────── */}
      <nav className="sticky top-0 z-50 border-b border-border bg-background/85 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-6 flex items-center justify-between h-16">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-indigo-600 rounded-md flex items-center justify-center">
              <Radio className="w-4 h-4 text-white" strokeWidth={2.25} />
            </div>
            <span className="font-semibold text-foreground text-base tracking-tight">TekWatch</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            <a href="#features" className="hover:text-foreground transition-colors">Platform</a>
            <a href="#how-it-works" className="hover:text-foreground transition-colors">How it works</a>
            <a href="#pricing" className="hover:text-foreground transition-colors">Pricing</a>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/login" className="hidden sm:block text-sm text-muted-foreground hover:text-foreground transition-colors px-3 py-1.5">
              Sign in
            </Link>
            <Link
              href="/overview"
              className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-md transition-colors"
            >
              Live Demo <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </nav>

      <main>
      {/* ── Hero + Dashboard Preview (forced-dark zone) ─────── */}
      <div className="relative overflow-hidden bg-background">
        <div className="absolute inset-0 bg-grid-pattern [mask-image:radial-gradient(ellipse_80%_60%_at_50%_0%,#000_30%,transparent_75%)]" />
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-indigo-600/10 rounded-full blur-[100px] pointer-events-none" />

        <section className="relative pt-20 pb-16 px-6">
          <div className="relative max-w-4xl mx-auto text-center">
            <div className="animate-fade-in-up inline-flex items-center gap-2 px-3 py-1.5 rounded-md border border-indigo-400/30 bg-indigo-500/10 text-indigo-300 text-xs font-mono font-medium tracking-wide mb-8">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
              AI-POWERED CLOUD INTELLIGENCE, BUILT FOR UK SMEs
            </div>

            <h1
              className="animate-fade-in-up text-4xl md:text-6xl font-semibold text-foreground leading-[1.1] mb-6 tracking-tight"
              style={{ animationDelay: '90ms' }}
            >
              Your AWS estate.<br />
              <span className="text-indigo-400">
                Fully visible. Always compliant.
              </span>
            </h1>

            <p
              className="animate-fade-in-up text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed"
              style={{ animationDelay: '180ms' }}
            >
              TekWatch gives UK SMEs real-time visibility across their AWS estate —
              with a proprietary AI engine that catches cost spikes, performance issues
              and security risks, and built-in UK GDPR and Cyber Essentials Plus
              compliance from day one.
            </p>

            <div
              className="animate-fade-in-up flex flex-col sm:flex-row gap-4 justify-center mb-16"
              style={{ animationDelay: '270ms' }}
            >
              <Link
                href="/overview"
                className="flex items-center justify-center gap-2 px-6 py-3.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-md transition-colors"
              >
                Launch Live Demo <ArrowRight className="w-4 h-4" />
              </Link>
              <a
                href="#how-it-works"
                className="flex items-center justify-center gap-2 px-6 py-3.5 border border-border text-foreground hover:bg-accent font-semibold rounded-md transition-colors"
              >
                See how it works
              </a>
            </div>

            {/* Stats */}
            <div
              className="animate-fade-in-up grid grid-cols-2 sm:flex sm:flex-nowrap items-center justify-center gap-y-6"
              style={{ animationDelay: '360ms' }}
            >
              {[
                ['20+', 'AWS services monitored'],
                ['<30 min', 'to first dashboard'],
                ['£79', 'starting price /mo'],
                ['0', 'firewall changes needed'],
              ].map(([val, label], i) => (
                <div key={label} className={`text-center px-6 py-2 ${i > 0 ? 'sm:border-l sm:border-border' : ''}`}>
                  <div className="font-mono text-2xl md:text-3xl font-semibold text-foreground [font-variant-numeric:proportional-nums]">{val}</div>
                  <div className="text-muted-foreground text-xs mt-1">{label}</div>
                </div>
              ))}
            </div>

            {/* Credibility strip */}
            <div
              className="animate-fade-in-up mt-14 rounded-lg border border-border bg-white/[0.03] px-6 py-6"
              style={{ animationDelay: '450ms' }}
            >
              <p className="text-center font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-5">
                Built by AWS-certified cloud engineers
              </p>
              <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-3">
                {[
                  { icon: Award, label: 'AWS Community Builder' },
                  { icon: BadgeCheck, label: '5× AWS Certified' },
                  { icon: ShieldCheck, label: 'ISC² Certified in Cybersecurity' },
                ].map(b => (
                  <div key={b.label} className="flex items-center gap-2 rounded-md border border-border bg-background/60 px-3.5 py-2 text-foreground/80 text-sm font-medium">
                    <b.icon className="w-4 h-4 text-indigo-400" />
                    {b.label}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ── Dashboard Preview ──────────────────────────── */}
        <section className="relative px-6 pb-24">
          <div className="max-w-5xl mx-auto">
            <div className="rounded-lg border border-border bg-card/90 backdrop-blur-xl overflow-hidden shadow-2xl shadow-black/50">
              {/* Fake browser tab strip — doubles as the view switcher */}
              <div className="flex items-center gap-1 px-3 pt-3 bg-black/20 border-b border-border overflow-x-auto">
                {previewTabs.map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    aria-current={activeTab === tab.id ? 'true' : undefined}
                    className={`flex-shrink-0 px-3.5 py-2 rounded-t-md text-xs font-medium font-mono transition-colors ${
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
                <div className="flex-1 mx-4">
                  <div className="h-5 rounded-md bg-background border border-border w-72 mx-auto flex items-center justify-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    <span className="text-xs text-muted-foreground font-mono">app.tekwatch.co.uk{activePath}</span>
                  </div>
                </div>
              </div>

              {/* Mock dashboard */}
              <div key={activeTab} className="p-5 space-y-3 animate-fade-in">
              {activeTab === 'overview' && (<>
                {/* Stat tiles */}
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

                {/* Chart row */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div className="md:col-span-2 min-w-0 rounded-xl border border-border bg-background/60 p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="text-xs text-muted-foreground">Daily AWS Spend — Last 30 Days</div>
                      <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                        <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-[2px] rounded-full bg-indigo-400" />This month</span>
                        <span className="flex items-center gap-1.5"><span className="inline-block w-3 border-t-2 border-dashed border-slate-500" />Last month</span>
                      </div>
                    </div>
                    <div aria-hidden="true"><ResponsiveContainer width="100%" height={170}>
                      <AreaChart data={spendData} margin={{ top: 14, right: 60, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="spendFill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#818cf8" stopOpacity={0.28} />
                            <stop offset="60%" stopColor="#818cf8" stopOpacity={0.06} />
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
                          label={{ value: 'AI flagged', position: 'top', fill: '#fbbf24', fontSize: 10, fontWeight: 600 }}
                        />
                      </AreaChart>
                    </ResponsiveContainer></div>
                  </div>

                  <div className="rounded-xl border border-border bg-background/60 p-4 flex flex-col">
                    <div className="text-xs text-muted-foreground mb-1">Compliance Posture</div>
                    <div className="relative w-full h-[104px] flex-shrink-0">
                      <div aria-hidden="true"><ResponsiveContainer width="100%" height="100%">
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

                {/* Per-service cost breakdown */}
                <div className="rounded-xl border border-border bg-background/60 p-4">
                  <div className="text-xs text-muted-foreground mb-2">Top AWS Services by Cost — This Month</div>
                  <div aria-hidden="true"><ResponsiveContainer width="100%" height={150}>
                    <BarChart data={serviceCostData} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                      <CartesianGrid horizontal={false} vertical={false} />
                      <XAxis type="number" hide />
                      <YAxis type="category" dataKey="service" tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} width={76} />
                      <Tooltip contentStyle={TIP_STY} formatter={(v: number) => [`£${v}`, 'Cost']} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                      <Bar dataKey="cost" radius={[0, 4, 4, 0]} barSize={14}>
                        {serviceCostData.map((d, i) => (
                          <Cell key={i} fill={d.cost === maxServiceCost ? '#fbbf24' : '#818cf8'} fillOpacity={d.cost === maxServiceCost ? 1 : 0.65} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer></div>
                </div>

                {/* Alert row */}
                <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-3 flex items-center gap-3">
                  <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
                  <div className="text-xs text-red-400 font-semibold tracking-wide">CRITICAL</div>
                  <div className="text-xs text-foreground/80 flex-1">CPU utilisation on web-server-01 is 92.4% (threshold: 80%)</div>
                  <div className="text-xs text-muted-foreground">15m ago</div>
                </div>
              </>)}

              {activeTab === 'security' && (<>
                {/* Summary tiles */}
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

                {/* Compliance posture bars */}
                <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-4">
                  <div className="text-xs text-muted-foreground mb-3">Compliance Posture — 4 frameworks</div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
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

                {/* GuardDuty findings */}
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
                  {/* Donut breakdown */}
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

                  {/* Forecast callout */}
                  <div className="rounded-xl border border-border bg-background/60 p-4 flex flex-col justify-between">
                    <div>
                      <div className="text-xs text-muted-foreground mb-2">Month-End Forecast</div>
                      <div className="font-mono text-3xl font-semibold text-foreground mb-1.5">£2,140</div>
                      <div className="flex items-center gap-1 text-xs font-medium text-amber-400">
                        <TrendingUp className="w-3 h-3" /> +8% <span className="text-muted-foreground font-normal">vs last month</span>
                      </div>
                    </div>
                    <div className="mt-4 flex items-start gap-2 rounded-lg border border-indigo-500/20 bg-indigo-500/5 p-2.5">
                      <Sparkles className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0 mt-0.5" />
                      <span className="text-[11px] text-foreground/80 leading-relaxed">
                        AI flagged 2 cost anomalies this month — largest: an idle RDS instance running 24/7 in eu-west-1.
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
                      <Bot className="w-3.5 h-3.5 text-indigo-400" />
                    </div>
                    <div className="space-y-2 flex-1">
                      <div className="rounded-2xl rounded-tl-sm bg-background border border-border text-foreground/90 text-sm leading-relaxed px-4 py-3">
                        {chatExchange.answer}
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {chatExchange.tools.map(t => (
                          <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-500/10 border border-indigo-500/20 text-indigo-300">
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
        </section>
      </div>

      {/* ── The Problem ──────────────────────────────────── */}
      <section className="relative px-6 py-24 border-t border-border overflow-hidden">
        <div className="absolute inset-0 bg-grid-pattern [mask-image:radial-gradient(ellipse_70%_50%_at_50%_50%,#000_20%,transparent_75%)] opacity-60 pointer-events-none" />
        <div className="relative max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <p className="text-xs font-mono font-semibold uppercase tracking-[0.2em] text-red-400 mb-3">The Problem</p>
            <h2 className="font-display text-3xl md:text-4xl font-bold text-foreground mb-4 tracking-tight">
              UK SMEs spend £28bn a year on AWS.<br className="hidden md:block" /> Most of it runs unmonitored.
            </h2>
            <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
              Enterprise tools like Datadog cost £800–£5,000/month and need a specialist to run.
              For 5.5 million UK SMEs, that&apos;s not a pricing tier — it&apos;s a locked door.
            </p>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {problemStats.map(s => (
              <div key={s.label} className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
                <s.icon className="w-5 h-5 text-red-400 mb-4" />
                <div className="font-mono text-3xl font-semibold text-foreground mb-2 [font-variant-numeric:proportional-nums]">{s.value}</div>
                <p className="text-sm text-muted-foreground leading-snug mb-3">{s.label}</p>
                <p className="text-[11px] text-muted-foreground/70">{s.source}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ─────────────────────────────────────── */}
      <section id="features" className="px-6 py-24 border-t border-border">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <p className="text-xs font-mono font-semibold uppercase tracking-[0.2em] text-indigo-500 dark:text-indigo-400 mb-3">Capabilities</p>
            <h2 className="font-display text-3xl md:text-4xl font-bold text-foreground mb-4 tracking-tight">Everything your team needs</h2>
            <p className="text-muted-foreground text-lg max-w-xl mx-auto">
              From real-time resource health to UK-specific compliance evidence — in one place.
            </p>
          </div>

          <div ref={featuresRef} className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {FEATURES.map((f, i) => (
              <FeatureCard key={f.title} f={f} index={i} inView={featuresInView} />
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works (forced-dark band) ─────────────── */}
      <div id="how-it-works" className="bg-background border-t border-border">
        <section className="px-6 py-24">
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-16">
              <p className="text-xs font-mono font-semibold uppercase tracking-[0.2em] text-indigo-400 mb-3">Onboarding</p>
              <h2 className="font-display text-3xl md:text-4xl font-bold text-foreground mb-4 tracking-tight">Up and running in 30 minutes</h2>
              <p className="text-muted-foreground text-lg">No sales call. No credit card. No specialist knowledge required.</p>
            </div>

            <div className="relative grid grid-cols-1 md:grid-cols-3 gap-10">
              {/* Connector line + a pulse that continuously travels it, left to right */}
              <div className="hidden md:block absolute top-6 left-[16.6%] right-[16.6%] h-px bg-border overflow-visible">
                <div className="absolute inset-0 bg-gradient-to-r from-indigo-500/50 via-violet-400/30 to-cyan-400/50" />
                <div
                  aria-hidden="true"
                  className="animate-travel-dot absolute top-1/2 w-2.5 h-2.5 -translate-y-1/2 -translate-x-1/2 rounded-full bg-indigo-400 shadow-[0_0_10px_2px_rgba(129,140,248,0.7)]"
                />
              </div>
              {ONBOARDING_STEPS.map((s, i) => (
                <div key={s.title} className="relative">
                  <div
                    className="relative z-10 w-12 h-12 rounded-full border border-indigo-400/30 bg-background flex items-center justify-center mb-5 animate-step-activate"
                    style={{ animationDelay: `${i * 1.5}s` }}
                  >
                    <span className="font-mono text-lg font-semibold text-indigo-400">{i + 1}</span>
                  </div>
                  <h3 className="font-semibold text-foreground mb-2">{s.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{s.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>

      {/* ── Pricing ──────────────────────────────────────── */}
      <section id="pricing" className="px-6 py-24 border-t border-border">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-10">
            <p className="text-xs font-mono font-semibold uppercase tracking-[0.2em] text-indigo-500 dark:text-indigo-400 mb-3">Pricing</p>
            <h2 className="font-display text-3xl md:text-4xl font-bold text-foreground mb-4 tracking-tight">Simple, predictable pricing</h2>
            <p className="text-muted-foreground text-lg">Self-service SaaS. No implementation fees, no sales call required.</p>
          </div>

          <div className="flex items-center justify-center gap-3 mb-10">
            <button
              onClick={() => setBilling('monthly')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${billing === 'monthly' ? 'bg-white/10 text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBilling('annual')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${billing === 'annual' ? 'bg-white/10 text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
            >
              Annual
              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-400">Save up to 15%</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {pricingTiers.map(p => {
              const displayPrice = billing === 'annual' ? Math.round(p.monthly * (1 - p.discount)) : p.monthly
              return (
                <div key={p.name} className={`rounded-lg border p-6 relative ${
                  p.highlight
                    ? 'border-indigo-500/50 bg-white/[0.05]'
                    : 'border-white/10 bg-white/[0.03]'
                }`}>
                  {p.highlight && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-600 text-white shadow-sm">
                      Most popular
                    </div>
                  )}
                  <h3 className="font-semibold text-foreground mb-1">{p.name}</h3>
                  <div className="flex items-baseline gap-1 mb-1">
                    <span className="font-mono text-3xl font-semibold text-foreground [font-variant-numeric:proportional-nums]">£{displayPrice}</span>
                    <span className="text-sm text-muted-foreground">/month</span>
                  </div>
                  <div className="h-5 mb-2">
                    {billing === 'annual' && (
                      <span className="text-xs text-emerald-400">Billed annually · save {Math.round(p.discount * 100)}%</span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground mb-5">{p.desc}</p>
                  <ul className="space-y-2 mb-6">
                    {p.features.map(f => (
                      <li key={f} className="flex items-center gap-2 text-sm text-foreground/80">
                        <Check className="w-4 h-4 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
                        {f}
                      </li>
                    ))}
                  </ul>
                  <Link
                    href="/overview"
                    className={`block text-center py-2.5 rounded-md text-sm font-semibold transition-colors ${
                      p.highlight
                        ? 'bg-indigo-600 hover:bg-indigo-500 text-white'
                        : 'border border-border text-foreground hover:bg-accent'
                    }`}
                  >
                    Start free trial
                  </Link>
                </div>
              )
            })}
          </div>
          <p className="text-center text-sm text-muted-foreground mt-8">
            Want it fully managed? Tek Tribe&apos;s Managed Cloud Services start from{' '}
            <span className="text-foreground font-medium">£500/month</span>, TekWatch included.
          </p>
        </div>
      </section>

      {/* ── CTA + Footer (forced-dark band) ─────────────── */}
      <div className="bg-background border-t border-border">
        <section className="relative px-6 py-24 overflow-hidden">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[220px] bg-indigo-600/8 rounded-full blur-[90px] pointer-events-none" />
          <div className="relative max-w-2xl mx-auto text-center">
            <h2 className="font-display text-3xl md:text-4xl font-bold text-foreground mb-4 tracking-tight">
              See your AWS estate, clearly.
            </h2>
            <p className="text-muted-foreground text-lg mb-8">
              Try the live demo — no account needed. Or start your 14-day free trial
              and see your own AWS environment in minutes.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="/overview"
                className="flex items-center justify-center gap-2 px-8 py-3.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-md transition-colors"
              >
                Launch Live Demo <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                href="/contact"
                className="flex items-center justify-center gap-2 px-8 py-3.5 border border-border text-foreground hover:bg-accent font-semibold rounded-md transition-colors"
              >
                Contact us
              </Link>
            </div>
          </div>
        </section>
      </div>
      </main>

      <footer className="bg-background px-6 pt-16 pb-8 border-t border-border">
          <div className="max-w-6xl mx-auto">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-10 mb-12">
              {/* Brand */}
              <div className="col-span-2 md:col-span-1">
                <div className="flex items-center gap-2.5 mb-4">
                  <div className="w-7 h-7 bg-indigo-600 rounded-md flex items-center justify-center">
                    <Radio className="w-3.5 h-3.5 text-white" strokeWidth={2.25} />
                  </div>
                  <span className="font-semibold text-foreground text-base">TekWatch</span>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed mb-5">
                  AI-powered AWS monitoring and UK compliance intelligence, built for SMEs by Tek Tribe Ltd —
                  the commercial evolution of an 8,000+ strong UK &amp; Nigeria tech community.
                </p>
                <div className="flex items-center gap-3">
                  <a
                    href="#"
                    aria-label="TekWatch on LinkedIn"
                    className="w-8 h-8 rounded-lg border border-white/10 bg-white/[0.03] hover:bg-white/[0.08] hover:border-white/20 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <Linkedin className="w-4 h-4" />
                  </a>
                  <a
                    href="#"
                    aria-label="Tek Talk on YouTube"
                    className="w-8 h-8 rounded-lg border border-white/10 bg-white/[0.03] hover:bg-white/[0.08] hover:border-white/20 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <Youtube className="w-4 h-4" />
                  </a>
                </div>
              </div>

              {/* Product */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground mb-4">Product</h3>
                <ul className="space-y-3 text-sm text-muted-foreground">
                  <li><a href="#features" className="hover:text-foreground transition-colors">Platform</a></li>
                  <li><a href="#how-it-works" className="hover:text-foreground transition-colors">How it works</a></li>
                  <li><a href="#pricing" className="hover:text-foreground transition-colors">Pricing</a></li>
                  <li><Link href="/overview" className="hover:text-foreground transition-colors">Live demo</Link></li>
                </ul>
              </div>

              {/* Company */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground mb-4">Company</h3>
                <ul className="space-y-3 text-sm text-muted-foreground">
                  <li><Link href="/login" className="hover:text-foreground transition-colors">Sign in</Link></li>
                  <li><Link href="/contact" className="hover:text-foreground transition-colors">Contact us</Link></li>
                </ul>
              </div>

              {/* Contact */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground mb-4">Contact</h3>
                <ul className="space-y-3 text-sm text-muted-foreground">
                  <li className="flex items-center gap-2">
                    <Mail className="w-3.5 h-3.5 flex-shrink-0" />
                    <a href="mailto:hello@tekwatch.co.uk" className="hover:text-foreground transition-colors">hello@tekwatch.co.uk</a>
                  </li>
                  <li className="flex items-center gap-2">
                    <MapPin className="w-3.5 h-3.5 flex-shrink-0" />
                    Glasgow, Scotland, UK
                  </li>
                </ul>
              </div>
            </div>

            <div className="pt-8 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-4">
              <p className="text-xs text-muted-foreground">© 2026 Tek Tribe Ltd. All rights reserved.</p>
              <p className="text-xs text-muted-foreground">Glasgow, Scotland · United Kingdom</p>
            </div>
          </div>
      </footer>
    </div>
  )
}

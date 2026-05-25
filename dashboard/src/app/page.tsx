'use client'

import Link from 'next/link'
import {
  Radio, Activity, Shield, DollarSign, Zap, Server,
  ArrowRight, Check, ChevronRight,
} from 'lucide-react'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#070c18] text-slate-200 overflow-x-hidden">

      {/* ── Nav ──────────────────────────────────────────── */}
      <nav className="sticky top-0 z-50 border-b border-white/[0.06] bg-[#070c18]/80 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-6 flex items-center justify-between h-14">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
              <Radio className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="font-bold text-white text-sm tracking-tight">Tek Watch</span>
          </div>
          <div className="hidden md:flex items-center gap-6 text-sm text-slate-400">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#how-it-works" className="hover:text-white transition-colors">How it works</a>
            <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/login" className="hidden sm:block text-sm text-slate-400 hover:text-white transition-colors">
              Sign in
            </Link>
            <Link
              href="/overview"
              className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Live Demo <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ─────────────────────────────────────────── */}
      <section className="relative pt-20 pb-28 px-6">
        {/* Background glow */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[900px] h-[500px] bg-indigo-600/10 rounded-full blur-3xl" />
        </div>

        <div className="relative max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-400 text-xs font-medium mb-8">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
            AI-Powered AWS Monitoring · Now in Early Access
          </div>

          <h1 className="text-5xl md:text-6xl font-bold text-white leading-tight mb-6 tracking-tight">
            Your AWS estate.<br />
            <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-cyan-400 bg-clip-text text-transparent">
              Fully visible. Always.
            </span>
          </h1>

          <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            Tek Watch monitors every corner of your AWS infrastructure in real time —
            with Claude AI catching cost spikes, performance drops, and security threats
            before they become incidents.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-14">
            <Link
              href="/overview"
              className="flex items-center justify-center gap-2 px-6 py-3.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/40"
            >
              Launch Live Demo <ArrowRight className="w-4 h-4" />
            </Link>
            <a
              href="#how-it-works"
              className="flex items-center justify-center gap-2 px-6 py-3.5 border border-white/[0.12] text-slate-300 hover:text-white hover:border-white/20 font-semibold rounded-xl transition-colors"
            >
              See how it works
            </a>
          </div>

          {/* Stats strip */}
          <div className="flex flex-wrap items-center justify-center gap-8 text-sm">
            {[
              ['12+', 'AWS services monitored'],
              ['5 min', 'collection interval'],
              ['<1 s', 'alert latency'],
              ['100%', 'multi-tenant'],
            ].map(([val, label]) => (
              <div key={label} className="text-center">
                <div className="text-2xl font-bold text-white">{val}</div>
                <div className="text-slate-500 text-xs mt-0.5">{label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Dashboard Preview ────────────────────────────── */}
      <section className="px-6 pb-20">
        <div className="max-w-5xl mx-auto">
          <div className="rounded-2xl border border-white/[0.08] bg-[#0a0f1e] overflow-hidden shadow-2xl shadow-black/50">
            {/* Mock browser chrome */}
            <div className="flex items-center gap-2 px-4 py-3 border-b border-white/[0.06] bg-white/[0.02]">
              <div className="w-3 h-3 rounded-full bg-red-500/60" />
              <div className="w-3 h-3 rounded-full bg-amber-500/60" />
              <div className="w-3 h-3 rounded-full bg-emerald-500/60" />
              <div className="flex-1 mx-4">
                <div className="h-5 rounded-md bg-white/[0.04] border border-white/[0.06] w-72 mx-auto flex items-center justify-center">
                  <span className="text-xs text-slate-500">app.tekwatch.io/overview</span>
                </div>
              </div>
            </div>
            {/* Mock dashboard */}
            <div className="p-5 space-y-4">
              {/* Stat cards row */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: 'Total Resources', value: '847', color: 'text-blue-400',    bg: 'bg-blue-500/10' },
                  { label: 'Active Alarms',   value: '3',   color: 'text-red-400',     bg: 'bg-red-500/10' },
                  { label: 'Security Findings',value: '2',  color: 'text-amber-400',   bg: 'bg-amber-500/10' },
                  { label: 'Monthly Cost',    value: '$4.2k', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
                ].map(s => (
                  <div key={s.label} className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-3">
                    <div className="text-xs text-slate-500 mb-1.5">{s.label}</div>
                    <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
                  </div>
                ))}
              </div>
              {/* Mock chart bars */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <div className="text-xs text-slate-500 mb-3">Daily Spend — Last 30 Days</div>
                <div className="flex items-end gap-1 h-20">
                  {[45,52,48,61,58,70,65,72,68,75,80,73,69,78,82,88,77,74,83,91,86,79,88,95,92,88,97,105,99,112].map((h, i) => (
                    <div key={i} className="flex-1 rounded-sm transition-all"
                      style={{ height: `${(h / 112) * 100}%`, background: i === 29 ? '#f97316' : '#6366f1', opacity: i === 29 ? 1 : 0.55 }} />
                  ))}
                </div>
              </div>
              {/* Alert row */}
              <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-3 flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse flex-shrink-0" />
                <div className="text-xs text-red-400 font-medium">CRITICAL</div>
                <div className="text-xs text-slate-300 flex-1">CPU utilisation on web-server-01 is 92.4% (threshold: 80%)</div>
                <div className="text-xs text-slate-500">15m ago</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Features ─────────────────────────────────────── */}
      <section id="features" className="px-6 py-20 border-t border-white/[0.06]">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">Everything your team needs</h2>
            <p className="text-slate-400 text-lg max-w-xl mx-auto">
              From real-time resource health to AI-generated cost recommendations — in one place.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                icon: Activity,
                color: 'text-indigo-400', bg: 'bg-indigo-500/10', border: 'border-indigo-500/20',
                title: 'Real-time Visibility',
                desc: 'EC2, RDS, Lambda, ECS, S3, SQS and 6 more services — metrics collected every 5 minutes across all your regions.',
                points: ['Multi-region discovery', '847+ resource types', 'Sub-minute alert latency'],
              },
              {
                icon: Zap,
                color: 'text-violet-400', bg: 'bg-violet-500/10', border: 'border-violet-500/20',
                title: 'AI Anomaly Detection',
                desc: 'Claude AI analyses your metric streams continuously, flagging unusual patterns that threshold alerts miss.',
                points: ['Powered by Claude AI', 'Cost, performance & security', 'Plain-English explanations'],
              },
              {
                icon: Shield,
                color: 'text-cyan-400', bg: 'bg-cyan-500/10', border: 'border-cyan-500/20',
                title: 'Security & Compliance',
                desc: 'GuardDuty findings, IAM credential health, ACM expiry, CloudTrail events — unified in one security view.',
                points: ['GuardDuty + Security Hub', 'IAM MFA & key rotation', 'Certificate expiry alerts'],
              },
              {
                icon: DollarSign,
                color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20',
                title: 'Cost Intelligence',
                desc: 'MTD spend, 30-day trends, per-service breakdowns, and AI-flagged cost anomalies before the bill arrives.',
                points: ['Daily spend trends', 'Per-service breakdown', 'AI cost anomaly alerts'],
              },
              {
                icon: Server,
                color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20',
                title: 'Multi-Customer Ready',
                desc: 'Built for MSPs. Each customer gets isolated data, their own dashboard, and a deployable CloudFormation agent.',
                points: ['Fully multi-tenant', 'One-click agent deploy', 'Customer isolation'],
              },
              {
                icon: Radio,
                color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/20',
                title: 'Lightweight Agent',
                desc: 'A single ECS Fargate task in the customer account. Read-only IAM, zero footprint, zero maintenance.',
                points: ['ECS Fargate', 'Read-only IAM role', 'Auto-deploy CloudFormation'],
              },
            ].map(f => (
              <div key={f.title} className={`rounded-xl border ${f.border} bg-white/[0.02] p-5 hover:bg-white/[0.04] transition-colors`}>
                <div className={`w-10 h-10 rounded-xl ${f.bg} ${f.border} border flex items-center justify-center mb-4`}>
                  <f.icon className={`w-5 h-5 ${f.color}`} />
                </div>
                <h3 className="font-semibold text-white mb-2">{f.title}</h3>
                <p className="text-sm text-slate-400 mb-4 leading-relaxed">{f.desc}</p>
                <ul className="space-y-1.5">
                  {f.points.map(p => (
                    <li key={p} className="flex items-center gap-2 text-xs text-slate-400">
                      <Check className={`w-3.5 h-3.5 ${f.color} flex-shrink-0`} />
                      {p}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────── */}
      <section id="how-it-works" className="px-6 py-20 border-t border-white/[0.06]">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">Up and running in minutes</h2>
            <p className="text-slate-400 text-lg">No agents to build. No dashboards to configure.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                step: '01',
                title: 'Admin creates customer',
                desc: 'In the Tek Watch admin portal, create a customer record. The platform generates a Customer ID and API key automatically.',
              },
              {
                step: '02',
                title: 'Deploy in 5 minutes',
                desc: 'Download a pre-filled CloudFormation template and deploy it to the customer\'s AWS account. The agent starts collecting immediately.',
              },
              {
                step: '03',
                title: 'Monitor & act',
                desc: 'The customer\'s live dashboard appears instantly — real-time metrics, AI anomaly alerts, cost trends, and security findings.',
              },
            ].map((s, i) => (
              <div key={s.step} className="relative">
                {i < 2 && (
                  <div className="hidden md:block absolute top-6 left-[calc(100%+1rem)] w-8 text-slate-600">
                    <ChevronRight className="w-5 h-5" />
                  </div>
                )}
                <div className="text-4xl font-bold text-white/[0.06] mb-3">{s.step}</div>
                <h3 className="font-semibold text-white mb-2">{s.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pricing ──────────────────────────────────────── */}
      <section id="pricing" className="px-6 py-20 border-t border-white/[0.06]">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">Simple, predictable pricing</h2>
            <p className="text-slate-400 text-lg">Per customer, per month. No surprise usage fees.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                name: 'Starter', price: '£149', period: '/mo per customer',
                desc: 'Perfect for small teams monitoring a single environment.',
                features: ['Up to 200 resources', '3 regions', 'Email alerts', '30-day history'],
                highlight: false,
              },
              {
                name: 'Professional', price: '£349', period: '/mo per customer',
                desc: 'For growing teams that need AI insights and deeper controls.',
                features: ['Up to 1,000 resources', 'Unlimited regions', 'AI anomaly detection', '90-day history', 'Slack + PagerDuty alerts', 'Cost optimisation'],
                highlight: true,
              },
              {
                name: 'Enterprise', price: 'Custom', period: '',
                desc: 'White-label, SLA guarantees, and volume discounts for large MSPs.',
                features: ['Unlimited resources', 'White-label branding', 'Dedicated support', 'Custom integrations', 'SOC 2 Type II'],
                highlight: false,
              },
            ].map(p => (
              <div key={p.name} className={`rounded-2xl border p-6 ${p.highlight
                ? 'border-indigo-500/40 bg-indigo-600/10 relative'
                : 'border-white/[0.08] bg-white/[0.02]'
              }`}>
                {p.highlight && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-600 text-white">
                    Most popular
                  </div>
                )}
                <h3 className="font-semibold text-white mb-1">{p.name}</h3>
                <div className="flex items-baseline gap-1 mb-3">
                  <span className="text-3xl font-bold text-white">{p.price}</span>
                  <span className="text-sm text-slate-400">{p.period}</span>
                </div>
                <p className="text-sm text-slate-400 mb-5">{p.desc}</p>
                <ul className="space-y-2 mb-6">
                  {p.features.map(f => (
                    <li key={f} className="flex items-center gap-2 text-sm text-slate-300">
                      <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
                <Link
                  href="/overview"
                  className={`block text-center py-2.5 rounded-xl text-sm font-semibold transition-colors ${p.highlight
                    ? 'bg-indigo-600 hover:bg-indigo-500 text-white'
                    : 'border border-white/[0.1] text-slate-300 hover:text-white hover:border-white/20'
                  }`}
                >
                  {p.price === 'Custom' ? 'Contact us' : 'Start free trial'}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────── */}
      <section className="px-6 py-20 border-t border-white/[0.06]">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            See your AWS estate, clearly.
          </h2>
          <p className="text-slate-400 text-lg mb-8">
            Try the live demo — no account needed. Or get in touch to discuss how Tek Watch fits your MSP.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/overview"
              className="flex items-center justify-center gap-2 px-8 py-3.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-indigo-500/20"
            >
              Launch Live Demo <ArrowRight className="w-4 h-4" />
            </Link>
            <a
              href="mailto:hello@tekwatch.io"
              className="flex items-center justify-center gap-2 px-8 py-3.5 border border-white/[0.12] text-slate-300 hover:text-white hover:border-white/20 font-semibold rounded-xl transition-colors"
            >
              Contact us
            </a>
          </div>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────── */}
      <footer className="px-6 py-8 border-t border-white/[0.06]">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 bg-indigo-600 rounded-md flex items-center justify-center">
              <Radio className="w-3 h-3 text-white" />
            </div>
            <span className="text-sm font-semibold text-white">Tek Watch</span>
            <span className="text-xs text-slate-500 ml-1">by Tek Tribe Ltd</span>
          </div>
          <p className="text-xs text-slate-500">© 2026 Tek Tribe Ltd. All rights reserved.</p>
          <div className="flex items-center gap-4 text-xs text-slate-500">
            <a href="mailto:support@tektribe.io" className="hover:text-slate-300 transition-colors">support@tektribe.io</a>
          </div>
        </div>
      </footer>
    </div>
  )
}

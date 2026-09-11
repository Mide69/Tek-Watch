'use client'

import { useState } from 'react'
import Link from 'next/link'
import axios from 'axios'
import { Check, ArrowRight } from 'lucide-react'
import { LogoMark } from '@/components/ui/Logo'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { useFixtureView } from '@/hooks/useFixtureView'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

type View = 'form' | 'sent'

export default function SignupPage() {
  const fixtureView = useFixtureView()
  const [view, setView] = useState<View>('form')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [company, setCompany] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const inputCls = 'w-full px-3.5 py-2.5 rounded-lg border border-border bg-card text-foreground placeholder:text-muted-foreground/70 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition'

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await axios.post(`${API_BASE_URL}/api/v1/signup`, { name, email, company: company || undefined })
      setView('sent')
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        setError("An account already exists for this email. Try signing in instead, or use the forgot-password link on the sign-in page.")
      } else if (axios.isAxiosError(err) && err.response?.status === 422) {
        setError('Please check your details and try again.')
      } else {
        setError('Something went wrong creating your account. Please try again shortly.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background flex">
      <ThemeToggle className="fixed top-4 right-4 z-50 bg-card/80 backdrop-blur" />
      {/* Left, branding panel */}
      <div className="hidden lg:flex lg:w-[42%] flex-col justify-center px-12 border-r border-border relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/10 via-transparent to-violet-500/10 dark:from-indigo-900/30 dark:to-violet-900/20 pointer-events-none" />
        <div className="relative">
          <Link href="/" className="flex items-center gap-3 mb-10">
            <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center">
              <LogoMark className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-foreground">TekWatch</span>
          </Link>
          <h2 className="text-3xl font-bold text-foreground mb-3 leading-snug">
            See your AWS estate clearly, from day one.
          </h2>
          <p className="text-muted-foreground text-sm leading-relaxed mb-10">
            Create your account, then deploy the read-only monitoring agent
            into your own AWS account in under 30 minutes. No firewall changes,
            no credit card to get started.
          </p>
          <ul className="space-y-3">
            {[
              'Real-time metrics across all regions',
              'Anomaly detection with plain-English explanations',
              'UK GDPR, Cyber Essentials & ISO 27001 checks',
              'Email and Slack alerts',
            ].map(f => (
              <li key={f} className="flex items-center gap-3 text-sm text-foreground/80">
                <div className="w-5 h-5 rounded-full bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center flex-shrink-0">
                  <Check className="w-3 h-3 text-indigo-600 dark:text-indigo-400" />
                </div>
                {f}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Right, form */}
      <div className="flex flex-1 items-center justify-center px-8 py-12">
        <div className="w-full max-w-md">
          {/* The desktop panel already links home; below lg it is hidden, so
              this was the one place a phone had no way back to the site. */}
          <Link href="/" className="flex items-center gap-2.5 mb-8 lg:hidden w-fit">
            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
              <LogoMark className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-foreground">TekWatch</span>
          </Link>

          {fixtureView ? (
            <div className="text-center">
              <div className="w-16 h-16 bg-indigo-500/15 border border-indigo-500/25 rounded-full flex items-center justify-center mx-auto mb-5">
                <LogoMark className="w-7 h-7 text-indigo-600 dark:text-indigo-400" />
              </div>
              <h1 className="text-xl font-bold text-foreground mb-2">This is a demo deployment</h1>
              <p className="text-muted-foreground text-sm mb-6 leading-relaxed">
                Account creation needs a live backend, which this demo doesn&apos;t run.
                Try the fully interactive demo instead, no account needed, or get in
                touch if you want a real account set up.
              </p>
              <div className="flex flex-col gap-3">
                <Link href="/overview" className="flex items-center justify-center gap-2 py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold transition-colors">
                  Launch Live Demo <ArrowRight className="w-3.5 h-3.5" />
                </Link>
                <Link href="/contact" className="text-sm text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300 transition-colors">
                  Contact us
                </Link>
              </div>
            </div>
          ) : view === 'form' ? (
            <>
              <div className="mb-8">
                <h1 className="text-2xl font-bold text-foreground">Create your account</h1>
                <p className="text-muted-foreground mt-1.5 text-sm">14 days free, no credit card required.</p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label htmlFor="name" className="block text-sm font-medium text-foreground/80 mb-1.5">Name</label>
                  <input id="name" type="text" required value={name}
                    onChange={e => setName(e.target.value)}
                    className={inputCls} placeholder="Jane Smith" />
                </div>
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-foreground/80 mb-1.5">Email</label>
                  <input id="email" type="email" required value={email}
                    onChange={e => setEmail(e.target.value)}
                    className={inputCls} placeholder="jane@company.co.uk" />
                </div>
                <div>
                  <label htmlFor="company-optional" className="block text-sm font-medium text-foreground/80 mb-1.5">
                    Company <span className="text-muted-foreground">(optional)</span>
                  </label>
                  <input id="company-optional" type="text" value={company}
                    onChange={e => setCompany(e.target.value)}
                    className={inputCls} placeholder="Company Ltd" />
                </div>

                {error && (
                  <div className="p-3 text-sm text-red-600 dark:text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg">{error}</div>
                )}

                <button type="submit" disabled={loading}
                  className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                  {loading ? 'Creating account…' : 'Create account'}
                </button>

                <p className="text-center text-sm text-muted-foreground">
                  Already have an account?{' '}
                  <Link href="/login" className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300 transition-colors">Sign in</Link>
                </p>
              </form>
            </>
          ) : (
            <div className="text-center">
              <div className="w-16 h-16 bg-emerald-500/15 border border-emerald-500/25 rounded-full flex items-center justify-center mx-auto mb-5">
                <Check className="w-7 h-7 text-emerald-600 dark:text-emerald-400" />
              </div>
              <h2 className="text-xl font-bold text-foreground mb-2">Check your email</h2>
              <p className="text-muted-foreground text-sm mb-6 leading-relaxed">
                We&apos;ve sent your Customer ID and password to {email}. Sign in, then
                head to the Agent page to deploy your monitoring agent.
              </p>
              <Link href="/login" className="text-sm text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300 transition-colors">
                Back to sign in
              </Link>
            </div>
          )}

          {!fixtureView && (
            <p className="mt-10 text-center text-xs text-muted-foreground/80">
              Questions before you sign up?{' '}
              <Link href="/contact" className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">Contact us</Link>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

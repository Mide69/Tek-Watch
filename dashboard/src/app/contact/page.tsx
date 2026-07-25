'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Radio, Mail, MapPin, Copy, Check, ArrowLeft, Send } from 'lucide-react'

export default function ContactPage() {
  const [form, setForm] = useState({ name: '', email: '', company: '', message: '' })
  const [sent, setSent] = useState(false)
  const [copied, setCopied] = useState(false)

  const email = 'hello@tekwatch.co.uk'

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }))
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const subject = `Contact from tekwatch.co.uk: ${form.name}`
    const body = [
      form.company && `Company: ${form.company}`,
      `Email: ${form.email}`,
      '',
      form.message,
    ].filter(Boolean).join('\n')
    window.location.href = `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
    setSent(true)
  }

  async function handleCopy() {
    await navigator.clipboard.writeText(email)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="dark min-h-screen bg-background text-foreground overflow-x-hidden">
      <nav className="sticky top-0 z-50 border-b border-border bg-background/85 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-6 flex items-center justify-between h-16">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-indigo-600 rounded-md flex items-center justify-center">
              <Radio className="w-4 h-4 text-white" strokeWidth={2.25} />
            </div>
            <span className="font-semibold text-foreground text-base tracking-tight">TekWatch</span>
          </Link>
          <Link href="/" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to home
          </Link>
        </div>
      </nav>

      <main className="relative overflow-hidden">
        <div className="absolute inset-0 bg-grid-pattern [mask-image:radial-gradient(ellipse_80%_60%_at_50%_0%,#000_30%,transparent_75%)]" />

        <section className="relative px-6 pt-16 pb-24 max-w-5xl mx-auto">
          <div className="mb-12 max-w-2xl">
            <p className="text-xs font-mono font-semibold uppercase tracking-[0.2em] text-indigo-400 mb-3">Contact</p>
            <h1 className="text-3xl md:text-4xl font-semibold text-foreground mb-4 tracking-tight">Talk to us</h1>
            <p className="text-muted-foreground text-lg leading-relaxed">
              Questions about TekWatch, Managed Cloud Services, or the Digital Careers Programme?
              Send us a message or email directly. We reply within one business day.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
            {/* Form */}
            <form onSubmit={handleSubmit} className="lg:col-span-3 rounded-lg border border-border bg-white/[0.03] p-6 space-y-5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div>
                  <label htmlFor="name" className="block text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2">Name</label>
                  <input
                    id="name" name="name" type="text" required
                    value={form.name} onChange={handleChange}
                    className="w-full rounded-md border border-border bg-background px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/50"
                    placeholder="Jane Smith"
                  />
                </div>
                <div>
                  <label htmlFor="email" className="block text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2">Email</label>
                  <input
                    id="email" name="email" type="email" required
                    value={form.email} onChange={handleChange}
                    className="w-full rounded-md border border-border bg-background px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/50"
                    placeholder="jane@company.co.uk"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="company" className="block text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2">
                  Company <span className="normal-case text-muted-foreground/60">(optional)</span>
                </label>
                <input
                  id="company" name="company" type="text"
                  value={form.company} onChange={handleChange}
                  className="w-full rounded-md border border-border bg-background px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/50"
                  placeholder="Company Ltd"
                />
              </div>

              <div>
                <label htmlFor="message" className="block text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2">Message</label>
                <textarea
                  id="message" name="message" required rows={5}
                  value={form.message} onChange={handleChange}
                  className="w-full rounded-md border border-border bg-background px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/50 resize-none"
                  placeholder="Tell us about your AWS setup and what you're looking for..."
                />
              </div>

              <button
                type="submit"
                className="flex items-center justify-center gap-2 w-full sm:w-auto px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm rounded-md transition-colors"
              >
                Send message <Send className="w-3.5 h-3.5" />
              </button>

              <p className="text-xs text-muted-foreground leading-relaxed">
                {sent
                  ? "Opening your email client to finish sending. If nothing happened, use the email address on the right instead, it's guaranteed to work."
                  : 'This opens a pre-filled email in your own mail client. No mail app configured? Email or copy the address on the right instead.'}
              </p>
            </form>

            {/* Direct contact */}
            <div className="lg:col-span-2 space-y-4">
              <div className="rounded-lg border border-border bg-white/[0.03] p-6">
                <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wide text-muted-foreground mb-3">
                  <Mail className="w-3.5 h-3.5" /> Email
                </div>
                <div className="flex items-center justify-between gap-3">
                  <a href={`mailto:${email}`} className="text-sm text-foreground hover:text-indigo-400 transition-colors truncate">{email}</a>
                  <button
                    type="button"
                    onClick={handleCopy}
                    aria-label="Copy email address"
                    className="flex-shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-border hover:border-white/20 hover:bg-white/[0.05] text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {copied ? <><Check className="w-3 h-3 text-emerald-400" /> Copied</> : <><Copy className="w-3 h-3" /> Copy</>}
                  </button>
                </div>
              </div>

              <div className="rounded-lg border border-border bg-white/[0.03] p-6">
                <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wide text-muted-foreground mb-3">
                  <MapPin className="w-3.5 h-3.5" /> Location
                </div>
                <p className="text-sm text-foreground">Glasgow, Scotland, UK</p>
                <p className="text-xs text-muted-foreground mt-1">Tek Tribe Ltd</p>
              </div>

              <div className="rounded-lg border border-indigo-500/20 bg-indigo-500/5 p-6">
                <p className="text-sm text-foreground/80 leading-relaxed">
                  Looking for hands-on help instead of self-service?{' '}
                  <span className="text-foreground font-medium">Managed Cloud Services</span> start from £500/month,
                  TekWatch included, just mention it in your message.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

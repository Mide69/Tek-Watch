'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { MessageSquare, Send, User, Loader2, X } from 'lucide-react'

/** The assistant's mark: the product's initials, not a robot. */
function AssistantMark() {
  return (
    <span className="w-7 h-7 rounded-md bg-primary text-primary-foreground text-[10px] font-bold tracking-wide flex items-center justify-center flex-shrink-0 mt-0.5">
      TW
    </span>
  )
}
import DashboardLayout from '@/components/layout/DashboardLayout'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import apiClient from '@/lib/api'
import { useFixtureView } from '@/hooks/useFixtureView'
import { cn } from '@/lib/utils'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolCalls?: string[]
  isError?: boolean
}

const SUGGESTED = [
  "Forecast this month's cloud spend",
  'How many EC2 instances do I have running?',
  'Are there any critical security alerts?',
  'Which AWS service costs the most?',
  'Give me an overview of my infrastructure',
  'Show me all active alerts',
]

/**
 * What the Assistant replies with in the demo.
 *
 * The demo has no Cognito session, so the real endpoint cannot be called. Every
 * figure below is read from the same fixtures the Overview, Cost and Security
 * pages render, so a visitor who checks one against another finds them equal.
 * The tools listed are the ones the live Assistant uses for that question.
 */
const DEMO_ANSWERS: { match: RegExp; content: string; toolCalls: string[] }[] = [
  {
    match: /forecast|this month|spend|bill/i,
    content:
      'Month to date you have spent $2,891.40. On the current trend the month lands at about ' +
      '$4,180.00, against $4,247.80 last month, so roughly 1.6% lower.\n\n' +
      'The movement worth watching is Lambda, up 38.7% month on month. Invocations are up, but ' +
      'cold-start duration has also risen sharply on acme-image-processor, which usually points ' +
      'to a recent package change rather than extra traffic.',
    toolCalls: ['get_cost_summary', 'get_cost_breakdown'],
  },
  {
    match: /ec2|instances/i,
    content:
      'You have 12 EC2 instances: 10 running and 2 stopped, all in eu-west-2.\n\n' +
      'web-server-01 is the one to look at. CPU is 92.4%, which is above the 80% threshold and ' +
      'has been for more than fifteen minutes.',
    toolCalls: ['get_ec2_instances', 'get_overview'],
  },
  {
    match: /critical|security alert|threat|guardduty/i,
    content:
      'One critical alert is open: CPU on web-server-01 at 92.4%, past the 80% threshold for ' +
      'over fifteen minutes.\n\n' +
      'On the compliance side, 9 of the 24 controls are failing, including public access on the ' +
      'acme-marketing-assets bucket and three IAM users without multi-factor authentication. ' +
      'Two controls could not be measured because AWS Config and Security Hub are switched off, ' +
      'and those are left out of the scores rather than counted as passes.',
    toolCalls: ['get_alerts', 'get_security_summary'],
  },
  {
    match: /costs? the most|most expensive|top service/i,
    content:
      'Amazon EC2, at $1,080.40 month to date, which is about 37% of the $2,891.40 total.\n\n' +
      'After that: RDS $620.80, CloudFront $340.20, S3 $220.60, Lambda $180.30 and ECS $160.40. ' +
      'EC2 is down 4.2% on last month, so the growth is not there. Lambda is the line moving, ' +
      'up 38.7%.',
    toolCalls: ['get_cost_breakdown', 'get_cost_summary'],
  },
  {
    match: /overview|infrastructure|estate|summary/i,
    content:
      'You are running 847 resources in eu-west-2, 7 more than the previous period.\n\n' +
      'Three alarms are active, one of them critical. Estimated monthly cost is $4,247.80, down ' +
      '3.2% on last month. On compliance, 9 of 24 controls are failing across UK GDPR, Cyber ' +
      'Essentials v3.3, ISO 27001:2022 and the FCA PS21/3 technical checks.\n\n' +
      'The thing I would deal with first is the acme-marketing-assets bucket, which lost its ' +
      'public access block three hours ago and is being served to the internet by a CloudFront ' +
      'distribution.',
    toolCalls: ['get_overview', 'get_alerts', 'get_security_summary'],
  },
  {
    match: /active alerts|all alerts|show me.*alerts/i,
    content:
      'Three alerts are active.\n\n' +
      'Critical, EC2: CPU on web-server-01 is 92.4%, above the 80% threshold for more than ' +
      'fifteen minutes.\n\n' +
      'Warning, RDS: active connections on prod-db-01 are 187 against a limit of 210, so the ' +
      'connection pool is 89% used.\n\n' +
      'Warning, Lambda: cold-start duration on acme-image-processor averaged 3.4 seconds over ' +
      'the last hour, which is 6.1 standard deviations above its seven-day baseline of 0.8 ' +
      'seconds.',
    toolCalls: ['get_alerts'],
  },
]

const DEMO_FALLBACK =
  'This demonstration answers the suggested questions from the sample account, so the figures ' +
  'match the other pages you can see. It does not call the live assistant, which needs a ' +
  'connected AWS account. Start a free trial to ask this against your own data.'

const TOOL_LABELS: Record<string, string> = {
  get_overview: 'Overview',
  get_cost_summary: 'Cost data',
  get_cost_breakdown: 'Cost breakdown',
  get_ec2_instances: 'EC2 instances',
  get_lambda_functions: 'Lambda functions',
  get_ecs_services: 'ECS services',
  get_rds_instances: 'RDS databases',
  get_s3_buckets: 'S3 buckets',
  get_alerts: 'Alerts',
  get_security_summary: 'Security',
}

function ToolBadge({ tool }: { tool: string }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium bg-muted border border-border text-muted-foreground">
      Read: {TOOL_LABELS[tool] ?? tool}
    </span>
  )
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  return (
    <div className={cn('flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}>
      {isUser ? (
        <div className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5 bg-muted border border-border">
          <User className="w-3.5 h-3.5 text-muted-foreground" />
        </div>
      ) : <AssistantMark />}

      <div className={cn('max-w-[75%] space-y-1.5 flex flex-col', isUser ? 'items-end' : 'items-start')}>
        <div className={cn(
          'px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap',
          isUser
            ? 'bg-primary text-primary-foreground rounded-tr-sm'
            : msg.isError
              ? 'bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-700 dark:text-red-300 rounded-tl-sm'
              : 'bg-card border border-border text-foreground rounded-tl-sm shadow-sm'
        )}>
          {msg.content}
        </div>
        {msg.toolCalls && msg.toolCalls.length > 0 && (
          <div className="flex flex-wrap gap-1 px-1">
            {msg.toolCalls.map((t, i) => <ToolBadge key={i} tool={t} />)}
          </div>
        )}
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <AssistantMark />
      <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-card border border-border shadow-sm">
        <div className="flex gap-1 items-center h-4">
          {[0, 1, 2].map(i => (
            <span
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce"
              style={{ animationDelay: `${i * 150}ms` }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

// The shell — sidebar, Home, Sign out — renders unconditionally. See the
// identical note in networking/page.tsx for why every page is split this way.
export default function ChatPage() {
  return (
    <DashboardLayout>
      <ErrorBoundary>
        <ChatContent />
      </ErrorBoundary>
    </DashboardLayout>
  )
}

function ChatContent() {
  const fixtureView = useFixtureView()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const send = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isLoading) return

    const userMsg: Message = { id: `u-${Date.now()}`, role: 'user', content: trimmed }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsLoading(true)

    const history = messages.map(m => ({ role: m.role, content: m.content }))

    // The demo has no session, so calling the API would 401 and bounce the
    // visitor to sign-in, ending the demo on their first click.
    if (fixtureView) {
      const hit = DEMO_ANSWERS.find(a => a.match.test(trimmed))
      await new Promise(r => setTimeout(r, 450))
      setMessages(prev => [...prev, {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: hit ? hit.content : DEMO_FALLBACK,
        toolCalls: hit ? hit.toolCalls : undefined,
      }])
      setIsLoading(false)
      textareaRef.current?.focus()
      return
    }

    try {
      const data = await apiClient.chat(trimmed, history)
      setMessages(prev => [...prev, {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: data.response,
        toolCalls: data.tool_calls,
      }])
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Something went wrong. Please try again.'
      setMessages(prev => [
        ...prev,
        { id: `e-${Date.now()}`, role: 'assistant', content: detail, isError: true },
      ])
    } finally {
      setIsLoading(false)
      textareaRef.current?.focus()
    }
  }, [isLoading, messages, fixtureView])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) }
  }

  const isEmpty = messages.length === 0

  return (
      <div className="flex flex-col h-[calc(100vh-7rem)] max-w-3xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-4 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
              <MessageSquare className="w-4 h-4 text-primary" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-foreground">Assistant</h1>
              <p className="text-xs text-muted-foreground">Questions about your AWS estate, answered from your own data</p>
            </div>
          </div>
          {!isEmpty && (
            <button
              onClick={() => { setMessages([]); setInput('') }}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded-lg hover:bg-accent border border-transparent hover:border-border"
            >
              <X className="w-3.5 h-3.5" />
              Clear
            </button>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-4 pr-1 pb-4">
          {isEmpty ? (
            <div className="flex flex-col items-center justify-center h-full gap-6 text-center">
              <div className="space-y-2">
                <MessageSquare className="w-6 h-6 text-muted-foreground mx-auto" />
                <p className="text-foreground font-medium">Ask about your AWS estate</p>
                <p className="text-muted-foreground text-sm">Answers come from the latest data your agent sent.</p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
                {SUGGESTED.map((q) => (
                  <button
                    key={q}
                    onClick={() => send(q)}
                    className="text-left px-4 py-3 rounded-xl border border-border bg-card hover:bg-accent hover:border-primary/30 text-sm text-muted-foreground hover:text-foreground transition-all shadow-sm"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
              {isLoading && <TypingIndicator />}
            </>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="flex-shrink-0 pt-3 border-t border-border">
          <div className="flex gap-3 items-end">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your infrastructure…"
              rows={1}
              disabled={isLoading}
              className="flex-1 resize-none bg-background border border-input rounded-xl px-4 py-3 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring focus:border-ring disabled:opacity-50 transition-colors max-h-32 overflow-y-auto shadow-sm"
              style={{ lineHeight: '1.5' }}
              onInput={e => {
                const el = e.currentTarget
                el.style.height = 'auto'
                el.style.height = `${Math.min(el.scrollHeight, 128)}px`
              }}
            />
            <button
              onClick={() => send(input)}
              disabled={!input.trim() || isLoading}
              className="w-10 h-10 rounded-xl bg-primary hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-colors flex-shrink-0 shadow-sm"
            >
              {isLoading
                ? <Loader2 className="w-4 h-4 text-primary-foreground animate-spin" />
                : <Send className="w-4 h-4 text-primary-foreground" />}
            </button>
          </div>
          <p className="text-[10px] text-muted-foreground/60 mt-2 text-center">
            Enter to send · Shift+Enter for newline · Powered by Claude
          </p>
        </div>
      </div>
  )
}

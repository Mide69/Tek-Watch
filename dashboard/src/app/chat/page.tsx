'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { MessageSquare, Send, Bot, User, Loader2, Sparkles, X } from 'lucide-react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import apiClient from '@/lib/api'
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
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-primary/10 border border-primary/20 text-primary">
      <Sparkles className="w-2.5 h-2.5" />
      {TOOL_LABELS[tool] ?? tool}
    </span>
  )
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  return (
    <div className={cn('flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}>
      <div className={cn(
        'w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5',
        isUser ? 'bg-primary' : 'bg-muted border border-border'
      )}>
        {isUser
          ? <User className="w-3.5 h-3.5 text-primary-foreground" />
          : <Bot className="w-3.5 h-3.5 text-primary" />}
      </div>

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
      <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 bg-muted border border-border">
        <Bot className="w-3.5 h-3.5 text-primary" />
      </div>
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

export default function ChatPage() {
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
  }, [isLoading, messages])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) }
  }

  const isEmpty = messages.length === 0

  return (
    <DashboardLayout>
      <div className="flex flex-col h-[calc(100vh-7rem)] max-w-3xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-4 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
              <MessageSquare className="w-4 h-4 text-primary" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-foreground">Ask AI</h1>
              <p className="text-xs text-muted-foreground">Natural language queries over your AWS infrastructure</p>
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
                <div className="w-14 h-14 rounded-2xl bg-primary/8 border border-primary/15 flex items-center justify-center mx-auto">
                  <Sparkles className="w-7 h-7 text-primary" />
                </div>
                <p className="text-foreground font-medium">Ask anything about your infrastructure</p>
                <p className="text-muted-foreground text-sm">Queries your live AWS data in real time.</p>
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
    </DashboardLayout>
  )
}

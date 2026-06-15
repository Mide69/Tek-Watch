'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { useAuth } from '@/hooks/useAuth'
import { useMessaging } from '@/hooks/useData'

export default function MessagingPage() {
  const { customerId }      = useAuth()
  const { data, isLoading } = useMessaging()

  if (isLoading || !data) {
    return (
      <DashboardLayout customerId={customerId || undefined}>
        <div className="space-y-6">
          <div className="h-8 w-36 bg-white/[0.06] rounded animate-pulse" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[0,1,2].map(i => <CardSkeleton key={i} />)}
          </div>
        </div>
      </DashboardLayout>
    )
  }

  const { sqs, sns } = data

  return (
    <DashboardLayout customerId={customerId || undefined}>
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-white">Messaging</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            SQS · SNS — {sqs.length} queues, {sns.length} topics
          </p>
        </div>

        {/* SQS */}
        <section>
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">SQS Queues</h2>
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06]">
                      {['Queue', 'Type', 'Visible', 'In Flight', 'Oldest (s)', 'Throughput/h', 'DLQ', 'DLQ Depth'].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sqs.map((q, idx) => (
                      <tr key={q.queue_name} className={`border-b border-white/[0.04] hover:bg-white/[0.02] ${idx % 2 ? 'bg-white/[0.01]' : ''}`}>
                        <td className="px-4 py-3 font-medium text-white max-w-[160px] truncate">{q.queue_name}</td>
                        <td className="px-4 py-3"><Badge variant="info">{q.type}</Badge></td>
                        <td className="px-4 py-3">
                          <span className={q.messages_visible > 1000 ? 'text-amber-400 font-semibold' : 'text-slate-300'}>
                            {q.messages_visible.toLocaleString()}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-300">{q.messages_inflight}</td>
                        <td className="px-4 py-3 text-xs text-slate-400">
                          {q.oldest_message_age > 0 ? `${q.oldest_message_age}s` : '—'}
                        </td>
                        <td className="px-4 py-3 text-slate-300">{q.throughput.toLocaleString()}</td>
                        <td className="px-4 py-3 text-xs text-slate-500 font-mono truncate max-w-[120px]">
                          {q.dlq ?? '—'}
                        </td>
                        <td className="px-4 py-3">
                          {q.dlq_count > 0
                            ? <Badge variant="error">{q.dlq_count}</Badge>
                            : <span className="text-xs text-emerald-400">0</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </section>

        {/* SNS */}
        <section>
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">SNS Topics</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {sns.map(topic => (
              <Card key={topic.topic_name}>
                <CardContent className="p-4">
                  <h3 className="font-semibold text-white mb-1">{topic.topic_name}</h3>
                  <p className="text-xs text-slate-500 mb-3">{topic.region}</p>
                  <div className="grid grid-cols-3 gap-3 text-center">
                    <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                      <div className="text-xs text-slate-500">Subscriptions</div>
                      <div className="text-lg font-bold text-slate-200 mt-0.5">{topic.subscriptions}</div>
                    </div>
                    <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                      <div className="text-xs text-slate-500">Msg/day</div>
                      <div className="text-lg font-bold text-slate-200 mt-0.5">{topic.messages_day.toLocaleString()}</div>
                    </div>
                    <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                      <div className="text-xs text-slate-500">Delivery %</div>
                      <div className={`text-lg font-bold mt-0.5 ${topic.delivery_success >= 99.5 ? 'text-emerald-400' : 'text-amber-400'}`}>
                        {topic.delivery_success.toFixed(1)}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      </div>
    </DashboardLayout>
  )
}

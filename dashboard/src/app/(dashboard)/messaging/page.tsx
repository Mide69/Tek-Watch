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
          <div className="h-8 w-36 bg-muted rounded animate-pulse" />
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
          <h1 className="text-2xl font-bold text-foreground">Messaging</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            SQS · SNS — {sqs.length} queues, {sns.length} topics
          </p>
        </div>

        {/* SQS */}
        <section>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">SQS Queues</h2>
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      {['Queue', 'Type', 'Visible', 'In Flight', 'Oldest (s)', 'Throughput/h', 'DLQ', 'DLQ Depth'].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-medium text-muted-foreground whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sqs.map((q, idx) => (
                      <tr key={q.queue_name} className={`border-b border-border/40 hover:bg-muted/30 ${idx % 2 ? 'bg-muted/10' : ''}`}>
                        <td className="px-4 py-3 font-medium text-foreground max-w-[160px] truncate">{q.queue_name}</td>
                        <td className="px-4 py-3"><Badge variant="info">{q.type}</Badge></td>
                        <td className="px-4 py-3">
                          <span className={q.messages_visible > 1000 ? 'text-amber-400 font-semibold' : 'text-foreground'}>
                            {q.messages_visible.toLocaleString()}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-foreground">{q.messages_inflight}</td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">
                          {q.oldest_message_age > 0 ? `${q.oldest_message_age}s` : '—'}
                        </td>
                        <td className="px-4 py-3 text-foreground">{q.throughput.toLocaleString()}</td>
                        <td className="px-4 py-3 text-xs text-muted-foreground font-mono truncate max-w-[120px]">
                          {q.dlq ?? '—'}
                        </td>
                        <td className="px-4 py-3">
                          {q.dlq_count > 0
                            ? <Badge variant="error">{q.dlq_count}</Badge>
                            : <span className="text-xs text-emerald-600 dark:text-emerald-400">0</span>}
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
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">SNS Topics</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {sns.map(topic => (
              <Card key={topic.topic_name}>
                <CardContent className="p-4">
                  <h3 className="font-semibold text-foreground mb-1">{topic.topic_name}</h3>
                  <p className="text-xs text-muted-foreground mb-3">{topic.region}</p>
                  <div className="grid grid-cols-3 gap-3 text-center">
                    <div className="p-2 rounded-lg bg-muted/30 border border-border">
                      <div className="text-xs text-muted-foreground">Subscriptions</div>
                      <div className="text-lg font-bold text-foreground mt-0.5">{topic.subscriptions}</div>
                    </div>
                    <div className="p-2 rounded-lg bg-muted/30 border border-border">
                      <div className="text-xs text-muted-foreground">Msg/day</div>
                      <div className="text-lg font-bold text-foreground mt-0.5">{topic.messages_day.toLocaleString()}</div>
                    </div>
                    <div className="p-2 rounded-lg bg-muted/30 border border-border">
                      <div className="text-xs text-muted-foreground">Delivery %</div>
                      <div className={`text-lg font-bold mt-0.5 ${topic.delivery_success >= 99.5 ? 'text-emerald-600 dark:text-emerald-600 dark:text-emerald-400' : 'text-amber-500 dark:text-amber-400'}`}>
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

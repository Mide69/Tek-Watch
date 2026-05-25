'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { useAuth } from '@/hooks/useAuth'
import { MOCK_SQS, MOCK_SNS } from '@/lib/mockData'

export default function MessagingPage() {
  const { loading: authLoading } = useAuth()

  if (authLoading) return (
    <DashboardLayout>
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500" />
      </div>
    </DashboardLayout>
  )

  return (
    <DashboardLayout>
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-white">Messaging</h1>
          <p className="text-slate-400 text-sm mt-0.5">SQS · SNS — {MOCK_SQS.length} queues, {MOCK_SNS.length} topics</p>
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
                      {['Queue', 'Visible Messages', 'In Flight', 'Oldest Msg Age', 'DLQ', 'DLQ Depth'].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {MOCK_SQS.map((q, idx) => (
                      <tr key={q.name} className={`border-b border-white/[0.04] hover:bg-white/[0.02] ${idx % 2 ? 'bg-white/[0.01]' : ''}`}>
                        <td className="px-4 py-3 font-medium text-white">{q.name}</td>
                        <td className="px-4 py-3">
                          <span className={q.messages_visible > 1000 ? 'text-amber-400 font-semibold' : 'text-slate-300'}>
                            {q.messages_visible.toLocaleString()}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-300">{q.messages_in_flight}</td>
                        <td className="px-4 py-3 text-xs text-slate-400">
                          {q.oldest_msg_age_s > 0 ? `${q.oldest_msg_age_s}s` : '—'}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-500 font-mono">{q.dlq}</td>
                        <td className="px-4 py-3">
                          {q.dlq_depth > 0
                            ? <Badge variant="error">{q.dlq_depth}</Badge>
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
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {MOCK_SNS.map(topic => (
              <Card key={topic.name}>
                <CardContent className="p-4">
                  <h3 className="font-semibold text-white mb-1">{topic.name}</h3>
                  <p className="text-xs font-mono text-slate-500 mb-3 truncate">{topic.arn.split(':').slice(-1)[0]}</p>
                  <div className="grid grid-cols-2 gap-3 text-center">
                    <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                      <div className="text-xs text-slate-500">Subscriptions</div>
                      <div className="text-lg font-bold text-slate-200 mt-0.5">{topic.subscriptions}</div>
                    </div>
                    <div className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                      <div className="text-xs text-slate-500">Msg/h</div>
                      <div className="text-lg font-bold text-slate-200 mt-0.5">{topic.messages_published_1h.toLocaleString()}</div>
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

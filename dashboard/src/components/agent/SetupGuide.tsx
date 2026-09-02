'use client'

import { Card, CardContent } from '@/components/ui/Card'
import { CheckCircle, Clock, Download, Eye, ShieldCheck, Trash2, Wifi } from 'lucide-react'

/**
 * How to install, run and remove the agent.
 *
 * The dashboard offered a download and nothing else. What the template creates,
 * what it can see, how long it takes, what to do when nothing arrives, and how
 * to get rid of it were all unwritten — so the only way to find out was to run
 * an unknown CloudFormation stack in your own AWS account and see what
 * happened. That is a reasonable thing to refuse to do, and a support email
 * waiting to happen.
 */

const STEPS = [
  {
    title: 'Download your template',
    body: 'Use the button above. It arrives filled in with your Customer ID, your agent key and the region to report to. Nothing needs editing.',
  },
  {
    title: 'Open CloudFormation in your AWS account',
    body: 'Sign in to the AWS console, choose the region you want to monitor from, and go to CloudFormation → Create stack → With new resources.',
  },
  {
    title: 'Upload the file',
    body: 'Choose "Upload a template file", select the .yaml you downloaded, and continue. Give the stack any name, "tek-watch-agent" is a sensible one.',
  },
  {
    title: 'Acknowledge the IAM notice and create',
    body: 'AWS asks you to confirm the stack may create IAM resources. It creates one read-only role, described below. Tick it and create the stack.',
  },
  {
    title: 'Wait for the first collection',
    body: 'The stack takes two to three minutes. The agent then runs every five minutes, so your dashboard fills in within about ten minutes of the stack completing.',
  },
]

const CREATES = [
  { icon: ShieldCheck, label: 'A read-only IAM role', detail: 'Scoped to describe and list calls. It cannot create, modify or delete anything in your account.' },
  { icon: Clock, label: 'An ECS Fargate task', detail: 'Runs for a few seconds every five minutes, then stops. Nothing runs between collections.' },
  { icon: Wifi, label: 'An EventBridge schedule', detail: 'Triggers that task. Outbound only, so no inbound firewall or security group changes are needed.' },
]

export function SetupGuide({ customerId }: { customerId?: string }) {
  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="p-5">
          <h3 className="font-semibold text-foreground mb-1">Installing the agent</h3>
          <p className="text-sm text-muted-foreground mb-5">
            About thirty minutes end to end, most of which is AWS creating the stack.
            You need permission to create a CloudFormation stack in the account you
            want monitored.
          </p>

          <ol className="space-y-4">
            {STEPS.map((step, i) => (
              <li key={step.title} className="flex gap-3.5">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/15 border border-primary/30 text-primary text-xs font-semibold flex items-center justify-center mt-0.5">
                  {i + 1}
                </span>
                <div>
                  <p className="text-sm font-medium text-foreground">{step.title}</p>
                  <p className="text-sm text-muted-foreground mt-0.5 leading-relaxed">{step.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5">
          <h3 className="font-semibold text-foreground mb-1">What it creates in your account</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Three resources, and nothing else. You can read the whole template before
            running it — it is plain YAML.
          </p>
          <div className="space-y-3.5">
            {CREATES.map(item => (
              <div key={item.label} className="flex gap-3">
                <item.icon className="w-4 h-4 text-primary flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-foreground">{item.label}</p>
                  <p className="text-sm text-muted-foreground mt-0.5 leading-relaxed">{item.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5">
          <div className="flex items-center gap-2 mb-3">
            <Eye className="w-4 h-4 text-primary" />
            <h3 className="font-semibold text-foreground">What it can see</h3>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Resource inventory and CloudWatch metrics: instance types and states, database
            sizes, function durations, queue depths, bucket counts, GuardDuty findings, IAM
            posture and Cost Explorer totals.
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed mt-2.5">
            It does not read the contents of anything. Not objects in your buckets, not rows
            in your databases, not environment variables, not application logs. The IAM role
            has no permission to, so this is a property of the role rather than a promise
            about the code.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5">
          <h3 className="font-semibold text-foreground mb-3">If nothing arrives</h3>
          <div className="space-y-3 text-sm">
            <div>
              <p className="font-medium text-foreground">The stack failed to create</p>
              <p className="text-muted-foreground mt-0.5 leading-relaxed">
                Open the stack in CloudFormation and read the Events tab, newest first. The
                first red row is the real cause; everything after it is rollback.
              </p>
            </div>
            <div>
              <p className="font-medium text-foreground">The stack created, but the agent stays silent</p>
              <p className="text-muted-foreground mt-0.5 leading-relaxed">
                Check the ECS cluster the stack created and open the most recent task&apos;s logs.
                An expired or mistyped agent key shows there as a rejected publish.
              </p>
            </div>
            <div>
              <p className="font-medium text-foreground">You have lost the agent key</p>
              <p className="text-muted-foreground mt-0.5 leading-relaxed">
                Download the template again with a new key. That replaces the old one, so any
                agent still running on it stops reporting until you update its stack.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5">
          <div className="flex items-center gap-2 mb-2">
            <Trash2 className="w-4 h-4 text-muted-foreground" />
            <h3 className="font-semibold text-foreground">Removing it</h3>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Delete the CloudFormation stack in your AWS account. That removes the role, the
            task and the schedule together, and nothing of ours is left behind. Your
            dashboard stops updating and the history already collected stays on your
            account{customerId ? ` (${customerId})` : ''} until you ask us to delete it.
          </p>
        </CardContent>
      </Card>

      <div className="flex items-start gap-2.5 rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-4 py-3">
        <CheckCircle className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
        <p className="text-sm text-emerald-700 dark:text-emerald-300">
          No inbound access is ever needed. The agent connects outward to us on 443 and
          nothing connects in, so there is no firewall rule, no VPN and no IP allow-list
          to arrange.
        </p>
      </div>

      <p className="text-xs text-muted-foreground">
        Stuck on any of it? <a href="mailto:support@tekwatch.io" className="text-primary hover:underline">support@tekwatch.io</a>
        {customerId ? <> — quote {customerId} and we can look at your account directly.</> : null}
      </p>
    </div>
  )
}

export { STEPS as AGENT_SETUP_STEPS }

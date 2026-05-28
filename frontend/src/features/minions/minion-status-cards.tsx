import { Activity, Check, MinusCircle, X } from 'lucide-react'

import type { components } from '@/shared/api/types.gen'

import { MinionComplianceSpark } from './minion-compliance-spark'
import { useMinionRuns } from './use-minion-runs'

type RunSummary = components['schemas']['MinionRunSummary']

const STATUS_ICON: Record<RunSummary['status'], React.ReactNode> = {
  blocked: <MinusCircle className="size-5 text-muted-foreground" />,
  changed: <Activity className="size-5 text-warning" />,
  healthy: <Check className="size-5 text-success" />,
  unhealthy: <X className="size-5 text-destructive" />,
}


export function MinionStatusCards({ minionId }: { minionId: string }) {
  const runs = useMinionRuns(minionId, 1)
  const last = runs.data?.runs[0]

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <LastHighstateCard last={last} />
      <ComplianceCard minionId={minionId} />
      <ActiveJobsCard />
    </div>
  )
}


function LastHighstateCard({ last }: { last: RunSummary | undefined }) {
  if (!last) {
    return (
      <Card title="Last highstate" hint="No runs ingested yet.">
        <p className="text-2xl text-muted-foreground">—</p>
      </Card>
    )
  }
  return (
    <Card title="Last highstate" hint={new Date(last.completed_at).toLocaleString()}>
      <div className="flex items-baseline gap-2">
        {STATUS_ICON[last.status]}
        <span className="text-2xl font-semibold capitalize">{last.status}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {last.pass_count} pass · {last.change_count} changed · {last.fail_count} failed / {last.total_count}
      </p>
    </Card>
  )
}


function ComplianceCard({ minionId }: { minionId: string }) {
  return (
    <Card title="Compliance" hint="Last 30 highstate runs">
      <div className="h-16">
        <MinionComplianceSpark minionId={minionId} />
      </div>
    </Card>
  )
}


function ActiveJobsCard() {
  return (
    <Card title="Active jobs" hint="Per-minion active tracking is roadmap.">
      <p className="text-2xl text-muted-foreground">—</p>
    </Card>
  )
}


function Card({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{title}</p>
      {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
      <div className="mt-2">{children}</div>
    </div>
  )
}

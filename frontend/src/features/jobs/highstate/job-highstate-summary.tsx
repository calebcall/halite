// frontend/src/features/jobs/highstate/job-highstate-summary.tsx
import { Lock, Server, ServerCog, ServerCrash } from 'lucide-react'

import type { JobHighstateAggregate } from './job-summary'

export function JobHighstateSummary({ stats }: { stats: JobHighstateAggregate }) {
  const hasFailures = stats.minionsWithFailures > 0
  const hasBlocked = stats.minionsBlocked > 0
  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <span className="inline-flex items-center gap-1.5">
          <Server className="h-4 w-4 text-muted-foreground" />
          <span className="font-semibold">{stats.totalMinions}</span>
          <span className="text-muted-foreground">minion{stats.totalMinions === 1 ? '' : 's'}</span>
        </span>
        <span className="text-muted-foreground">·</span>
        <span className="inline-flex items-center gap-1.5">
          <ServerCog className="h-4 w-4 text-success" />
          <span className="font-semibold">{stats.minionsAllSuccess}</span>
          <span className="text-muted-foreground">succeeded</span>
        </span>
        <span className="text-muted-foreground">·</span>
        <span className={`inline-flex items-center gap-1.5 ${hasFailures ? 'text-destructive' : ''}`}>
          <ServerCrash className={`h-4 w-4 ${hasFailures ? 'text-destructive' : 'text-muted-foreground'}`} />
          <span className="font-semibold">{stats.minionsWithFailures}</span>
          <span className={hasFailures ? '' : 'text-muted-foreground'}>with failures</span>
        </span>
        {hasBlocked && (
          <>
            <span className="text-muted-foreground">·</span>
            <span className="inline-flex items-center gap-1.5 text-warning">
              <Lock className="h-4 w-4" />
              <span className="font-semibold">{stats.minionsBlocked}</span>
              <span>blocked</span>
            </span>
          </>
        )}
        {stats.minionsNonHighstate > 0 && (
          <>
            <span className="text-muted-foreground">·</span>
            <span className="inline-flex items-center gap-1.5 text-muted-foreground">
              <span className="font-semibold">{stats.minionsNonHighstate}</span>
              <span>non-state output</span>
            </span>
          </>
        )}
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span><span className="font-semibold text-foreground">{stats.totalStatesWithChanges}</span> state changes</span>
        <span>·</span>
        <span className={stats.totalStateFailures > 0 ? 'text-destructive' : undefined}>
          <span className="font-semibold">{stats.totalStateFailures}</span> state failure{stats.totalStateFailures === 1 ? '' : 's'} across the run
        </span>
      </div>
    </div>
  )
}

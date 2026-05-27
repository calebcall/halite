import { AlertTriangle, Clock } from 'lucide-react'
import { useMemo, useState } from 'react'

import { cn } from '@/lib/utils'

import { TimelineFilters, type TimelineFiltersValue } from './timeline-filters'
import { TimelineGrid } from './timeline-grid'
import { useJobsTimeline } from './use-jobs-timeline'

import type { components } from '@/shared/api/types.gen'
type Bar = components['schemas']['TimelineBar']


function formatRelative(d: Date): string {
  const diff = Date.now() - d.getTime()
  const sec = Math.round(diff / 1000)
  if (sec < 60) return 'just now'
  const min = Math.round(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.round(min / 60)
  if (hr < 24) return `${hr}h ago`
  return `${Math.round(hr / 24)}d ago`
}


export function TimelinePage() {
  const [filters, setFilters] = useState<TimelineFiltersValue>({
    function_filter: '',
    group_by: 'function',
    include_system: false,
    user: '',
    window: '24h',
  })
  const [hovered, setHovered] = useState<Bar | null>(null)

  const query = useMemo(
    () => ({
      function_filter: filters.function_filter || undefined,
      group_by: filters.group_by,
      include_system: filters.include_system,
      user: filters.user || undefined,
      window: filters.window,
    }),
    [filters],
  )
  const { data, isLoading, isError } = useJobsTimeline(query)

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Jobs timeline</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Recent activity from <code className="text-xs">jobs_index</code>. Color = function category.
            State.* bars use highstate result for fill.
          </p>
        </div>
        {data && (
          <span
            className={cn(
              'inline-flex items-center gap-1.5 text-xs',
              // Only flag a warning when we have NO data AND no active-jids
              // refresh has happened — that's the genuine "scheduler is off"
              // signal. Bars present is proof the scheduler ran at least once.
              data.total_bars > 0 || data.last_polled_at
                ? 'text-muted-foreground'
                : 'text-warning',
            )}
            title={data.last_polled_at ? new Date(data.last_polled_at).toLocaleString() : undefined}
          >
            {data.total_bars > 0 || data.last_polled_at ? (
              <>
                <Clock className="size-3" />
                {data.last_polled_at && (
                  <>Updated {formatRelative(new Date(data.last_polled_at))} · </>
                )}
                {data.total_bars} bars
              </>
            ) : (
              <>
                <AlertTriangle className="size-3" />
                Jobs scheduler not running — enable in Settings → Pollers
              </>
            )}
          </span>
        )}
      </header>

      <TimelineFilters value={filters} onChange={setFilters} />

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {isError && <p className="text-sm text-destructive">Failed to load timeline.</p>}
      {data && data.total_bars === 0 && (
        <p className="rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          No jobs in the selected window.
          {!data.active_known && ' The jobs-index poller may not be running.'}
        </p>
      )}
      {data && data.total_bars > 0 && (
        <TimelineGrid data={data} onBarHover={setHovered} />
      )}

      {hovered && (
        <div className="fixed bottom-4 right-4 z-40 max-w-md rounded-md border border-border bg-popover p-3 text-xs shadow-lg">
          <div className="font-mono text-sm">{hovered.function}</div>
          <div className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
            <span className="text-muted-foreground">jid</span>
            <span className="font-mono">{hovered.jid}</span>
            <span className="text-muted-foreground">target</span>
            <span className="font-mono">{hovered.target ?? '—'}</span>
            <span className="text-muted-foreground">user</span>
            <span>{hovered.user ?? '—'}</span>
            <span className="text-muted-foreground">started</span>
            <span>{new Date(hovered.started_at).toLocaleString()}</span>
            <span className="text-muted-foreground">status</span>
            <span>{hovered.status}</span>
            {hovered.minion_count !== null && (
              <>
                <span className="text-muted-foreground">minions</span>
                <span>{hovered.minion_count}</span>
              </>
            )}
            {hovered.failed_minion_count !== null && hovered.failed_minion_count > 0 && (
              <>
                <span className="text-muted-foreground">failed</span>
                <span className="text-destructive">{hovered.failed_minion_count}</span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

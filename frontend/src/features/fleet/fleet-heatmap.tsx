import { useMemo, useState } from 'react'

import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import type { components } from '@/shared/api/types.gen'
import { useFleetHealth } from './use-fleet'

type Minion = components['schemas']['MinionHealthOut']
type Status = Minion['status']

const STATUS_STYLE: Record<Status, string> = {
  blocked: 'bg-warning/15 hover:bg-warning/25 border-warning/40 text-warning-foreground',
  changed: 'bg-warning/20 hover:bg-warning/30 border-warning/50 text-warning-foreground',
  fail: 'bg-destructive/15 hover:bg-destructive/25 border-destructive/50 text-destructive',
  pass: 'bg-success/15 hover:bg-success/25 border-success/40 text-success',
  stale: 'bg-muted/40 hover:bg-muted/60 border-muted-foreground/30 text-muted-foreground',
  unknown: 'bg-muted/30 hover:bg-muted/50 border-border text-muted-foreground',
}

const STATUS_LABEL: Record<Status, string> = {
  blocked: 'blocked',
  changed: 'changed',
  fail: 'fail',
  pass: 'pass',
  stale: 'stale',
  unknown: 'unknown',
}

export function FleetHeatmap({
  onTileClick,
}: {
  onTileClick: (minion: Minion) => void
}) {
  const { data, isError, isLoading } = useFleetHealth()
  const [filter, setFilter] = useState('')

  const filtered = useMemo(() => {
    const all = data?.minions ?? []
    if (!filter.trim()) return all
    const q = filter.trim().toLowerCase()
    return all.filter((m) => m.minion_id.toLowerCase().includes(q))
  }, [data, filter])

  return (
    <section className="rounded-lg border border-border/80 bg-card p-4 shadow-sm">
      <header className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold tracking-tight text-foreground">
            Fleet health
          </h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Last highstate per minion. Hover for status; click for details.
          </p>
        </div>
        <Input
          aria-label="Filter minions"
          className="h-8 max-w-[180px] shrink-0"
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter…"
          value={filter}
        />
      </header>

      {isLoading && <FleetHeatmapSkeleton />}
      {isError && (
        <p className="mt-3 text-sm text-destructive">
          Couldn&apos;t load fleet health.
        </p>
      )}
      {!isLoading && !isError && (
        <>
          <Legend />
          <div className="mt-3 grid grid-cols-[repeat(auto-fill,minmax(2.5rem,1fr))] gap-1.5">
            {filtered.map((m) => (
              <button
                key={m.minion_id}
                aria-label={`${m.minion_id} ${STATUS_LABEL[m.status]}`}
                className={cn(
                  'h-9 rounded border text-xs font-medium transition-colors',
                  STATUS_STYLE[m.status],
                )}
                onClick={() => onTileClick(m)}
                title={`${m.minion_id} — ${STATUS_LABEL[m.status]} (${m.pass_count}/${m.total_count})`}
                type="button"
              >
                {m.minion_id.slice(0, 4)}
              </button>
            ))}
            {filtered.length === 0 && (
              <p className="col-span-full py-6 text-center text-sm text-muted-foreground">
                {data?.total_minions === 0
                  ? 'No fleet data yet — give the scheduler a few minutes.'
                  : 'No minions match the filter.'}
              </p>
            )}
          </div>
        </>
      )}
    </section>
  )
}

function Legend() {
  const entries: { label: string; status: Status }[] = [
    { label: 'Pass', status: 'pass' },
    { label: 'Changed', status: 'changed' },
    { label: 'Failed', status: 'fail' },
    { label: 'Blocked', status: 'blocked' },
    { label: 'Stale (>2d)', status: 'stale' },
  ]
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
      {entries.map((e) => (
        <span key={e.status} className="inline-flex items-center gap-1.5">
          <span
            className={cn('inline-block h-3 w-3 rounded border', STATUS_STYLE[e.status])}
          />
          {e.label}
        </span>
      ))}
    </div>
  )
}

function FleetHeatmapSkeleton() {
  return (
    <div
      aria-hidden
      className="mt-3 grid grid-cols-[repeat(auto-fill,minmax(2.5rem,1fr))] gap-1.5"
    >
      {Array.from({ length: 60 }).map((_, i) => (
        <div
          key={i}
          className="h-9 animate-pulse rounded border border-border bg-muted/40"
        />
      ))}
    </div>
  )
}

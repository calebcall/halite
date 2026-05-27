import { Link } from '@tanstack/react-router'
import { useMemo } from 'react'

import { cn } from '@/lib/utils'

import type { components } from '@/shared/api/types.gen'

type Timeline = components['schemas']['TimelineOut']
type Group = components['schemas']['TimelineGroup']
type Bar = components['schemas']['TimelineBar']
type Status = Bar['status']
type Category = Bar['category']

const ROW_HEIGHT = 28
const ROW_GAP = 4
const LABEL_GUTTER_PX = 220
const MIN_BAR_PCT = 0.5 // Minimum bar width as % of total

// Category drives the BASE color of the bar; status overrides for state-result.
const CATEGORY_TINT: Record<Category, string> = {
  cmd: 'bg-violet-500',
  manage: 'bg-slate-500',
  other: 'bg-stone-500',
  pkg: 'bg-indigo-500',
  runner: 'bg-slate-500',
  service: 'bg-cyan-500',
  state: 'bg-emerald-500',
  test: 'bg-sky-500',
  wheel: 'bg-slate-500',
}

const STATUS_OVERRIDE: Partial<Record<Status, string>> = {
  changed: 'bg-warning',
  failed: 'bg-destructive',
  running: 'bg-primary animate-pulse',
}

function _classify(bar: Bar): string {
  return STATUS_OVERRIDE[bar.status] ?? CATEGORY_TINT[bar.category]
}

export function TimelineGrid({
  data,
  onBarHover,
}: {
  data: Timeline
  onBarHover?: (bar: Bar | null) => void
}) {
  const startMs = new Date(data.window_start).getTime()
  const endMs = new Date(data.window_end).getTime()
  const totalMs = Math.max(endMs - startMs, 1)

  return (
    <div className="relative overflow-x-auto rounded-lg border border-border bg-card">
      <div className="flex">
        {/* Sticky label gutter */}
        <div
          className="sticky left-0 z-10 shrink-0 border-r border-border bg-card"
          style={{ width: LABEL_GUTTER_PX }}
        >
          <div className="h-8 border-b border-border bg-muted/40 px-3 py-1.5 text-xs font-medium text-muted-foreground">
            {data.group_by === 'function' ? 'Function' : 'User'}
          </div>
          {data.groups.map((g) => (
            <div
              key={g.key}
              className="flex items-center gap-2 border-b border-border px-3 text-xs"
              style={{ height: ROW_HEIGHT + ROW_GAP }}
            >
              <span
                aria-hidden
                className={cn('inline-block size-2 shrink-0 rounded', CATEGORY_TINT[g.category])}
              />
              <span className="truncate font-mono">{g.label}</span>
              <span className="ml-auto shrink-0 text-muted-foreground">{g.bar_count}</span>
            </div>
          ))}
        </div>

        {/* Chart area */}
        <div className="relative flex-1" style={{ minWidth: 600 }}>
          <TimelineAxis windowEnd={data.window_end} windowStart={data.window_start} />
          <div>
            {data.groups.map((g) => (
              <TimelineRow
                key={g.key}
                group={g}
                onHover={onBarHover}
                startMs={startMs}
                totalMs={totalMs}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function TimelineAxis({
  windowEnd,
  windowStart,
}: {
  windowEnd: string
  windowStart: string
}) {
  const ticks = useMemo(() => {
    const start = new Date(windowStart)
    const end = new Date(windowEnd)
    const out: Date[] = []
    for (let i = 0; i <= 5; i++) {
      out.push(new Date(start.getTime() + (i / 5) * (end.getTime() - start.getTime())))
    }
    return out
  }, [windowStart, windowEnd])
  return (
    <div className="relative h-8 border-b border-border bg-muted/40 text-[10px] text-muted-foreground">
      {ticks.map((t, i) => (
        <span
          key={i}
          className="absolute top-1.5 -translate-x-1/2"
          style={{ left: `${(i / 5) * 100}%` }}
        >
          {t.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
        </span>
      ))}
    </div>
  )
}

function TimelineRow({
  group,
  onHover,
  startMs,
  totalMs,
}: {
  group: Group
  onHover?: (bar: Bar | null) => void
  startMs: number
  totalMs: number
}) {
  return (
    <div
      className="relative border-b border-border"
      style={{ height: ROW_HEIGHT + ROW_GAP }}
    >
      {group.bars.map((bar) => (
        <TimelineBarRect
          key={bar.jid}
          bar={bar}
          onHover={onHover}
          startMs={startMs}
          totalMs={totalMs}
        />
      ))}
    </div>
  )
}

function TimelineBarRect({
  bar,
  onHover,
  startMs,
  totalMs,
}: {
  bar: Bar
  onHover?: (bar: Bar | null) => void
  startMs: number
  totalMs: number
}) {
  const bStart = new Date(bar.started_at).getTime()
  const bEnd = bar.completed_at
    ? new Date(bar.completed_at).getTime()
    : bar.status === 'running'
      ? startMs + totalMs // running → extend to window end
      : bStart + 60_000 // unknown completion → 1-min marker
  const xPct = Math.max(0, ((bStart - startMs) / totalMs) * 100)
  const wPct = Math.max(((bEnd - bStart) / totalMs) * 100, MIN_BAR_PCT)
  const cls = _classify(bar)
  return (
    <Link
      aria-label={`${bar.function} ${bar.status}`}
      className={cn(
        'absolute rounded border border-border/40 shadow-sm transition-colors hover:opacity-90',
        cls,
      )}
      onMouseEnter={() => onHover?.(bar)}
      onMouseLeave={() => onHover?.(null)}
      params={{ jid: bar.jid }}
      style={{
        height: ROW_HEIGHT - ROW_GAP,
        left: `${xPct}%`,
        top: ROW_GAP / 2,
        width: `${wPct}%`,
      }}
      title={`${bar.function} · ${bar.target ?? '?'} · ${bar.status}`}
      to="/jobs/$jid"
    />
  )
}

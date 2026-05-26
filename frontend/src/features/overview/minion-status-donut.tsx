import { useMemo, useState } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

import type { MinionStatus } from '@/features/minions/api'
import { ChartTooltip } from './chart-tooltip'

interface MinionStatusDonutProps {
  minions: ReadonlyArray<{ status: MinionStatus }>
}

type Slice = {
  key: MinionStatus
  label: string
  value: number
  color: string
}

const STATUS_ORDER: MinionStatus[] = [
  'online',
  'offline',
  'pending',
  'rejected',
  'denied',
]

const STATUS_LABEL: Record<MinionStatus, string> = {
  online: 'Online',
  offline: 'Offline',
  pending: 'Pending',
  rejected: 'Rejected',
  denied: 'Denied',
}

/** Per-slice color using semantic tokens already defined in index.css. */
function colorFor(status: MinionStatus): string {
  // Values reference CSS vars via the helper at the bottom of this file.
  switch (status) {
    case 'online':
      return 'hsl(var(--success))'
    case 'offline':
      return 'hsl(var(--muted-foreground) / 0.55)'
    case 'pending':
      return 'hsl(var(--warning))'
    case 'rejected':
    case 'denied':
      return 'hsl(var(--destructive))'
  }
}

export function MinionStatusDonut({ minions }: MinionStatusDonutProps) {
  const [activeKey, setActiveKey] = useState<MinionStatus | null>(null)

  const { slices, total } = useMemo(() => {
    const counts = new Map<MinionStatus, number>()
    for (const m of minions) {
      counts.set(m.status, (counts.get(m.status) ?? 0) + 1)
    }
    const data: Slice[] = STATUS_ORDER
      .map((key) => ({
        key,
        label: STATUS_LABEL[key],
        value: counts.get(key) ?? 0,
        color: colorFor(key),
      }))
      .filter((s) => s.value > 0)
    return { slices: data, total: minions.length }
  }, [minions])

  // Highlight the "online" count as the headline number — the most useful at-a-glance metric.
  const onlineCount = useMemo(
    () => slices.find((s) => s.key === 'online')?.value ?? 0,
    [slices],
  )

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <div className="relative h-44 w-full sm:w-1/2">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Tooltip
              cursor={false}
              content={
                <ChartTooltip
                  valueFormatter={(v) =>
                    `${v.toLocaleString()} (${
                      total > 0 ? Math.round((v / total) * 100) : 0
                    }%)`
                  }
                />
              }
            />
            <Pie
              data={slices}
              dataKey="value"
              nameKey="label"
              innerRadius="62%"
              outerRadius="90%"
              paddingAngle={slices.length > 1 ? 2 : 0}
              stroke="hsl(var(--card))"
              strokeWidth={2}
              isAnimationActive
              animationBegin={50}
              animationDuration={500}
              onMouseEnter={(_, idx) => setActiveKey(slices[idx]?.key ?? null)}
              onMouseLeave={() => setActiveKey(null)}
            >
              {slices.map((s) => (
                <Cell
                  key={s.key}
                  fill={s.color}
                  opacity={
                    activeKey === null || activeKey === s.key ? 1 : 0.35
                  }
                  style={{ transition: 'opacity 200ms ease-out' }}
                />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        {/* Center label — uses tabular numerals to prevent layout jitter */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-2xl font-semibold tabular-nums text-foreground">
            {onlineCount.toLocaleString()}
          </span>
          <span className="text-[10px] font-medium uppercase tracking-[0.15em] text-muted-foreground">
            Online
          </span>
        </div>
      </div>

      {/* Interactive legend — hovering a row dims the other slices. */}
      <ul
        className="flex w-full flex-col gap-1 px-3 sm:w-1/2"
        role="list"
        aria-label="Minion status breakdown"
      >
        {slices.length === 0 && (
          <li className="text-xs text-muted-foreground">No minions reported.</li>
        )}
        {slices.map((s) => {
          const dimmed = activeKey !== null && activeKey !== s.key
          return (
            <li
              key={s.key}
              onMouseEnter={() => setActiveKey(s.key)}
              onMouseLeave={() => setActiveKey(null)}
              className="flex cursor-default items-center justify-between gap-3 rounded-md px-2 py-1 text-xs transition-colors hover:bg-accent"
              style={{ opacity: dimmed ? 0.5 : 1 }}
            >
              <span className="flex items-center gap-2">
                <span
                  aria-hidden
                  className="h-2.5 w-2.5 rounded-[2px]"
                  style={{ backgroundColor: s.color }}
                />
                <span className="text-muted-foreground">{s.label}</span>
              </span>
              <span className="font-medium tabular-nums text-foreground">
                {s.value.toLocaleString()}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

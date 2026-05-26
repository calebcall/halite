import { useMemo } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { JobActivityBucket } from '@/features/jobs/api'
import { ChartTooltip } from './chart-tooltip'

interface JobActivityAreaProps {
  /** Server-side hourly buckets, oldest first. */
  buckets: ReadonlyArray<JobActivityBucket>
}

type Row = {
  /** label shown on the X axis ("13:00") */
  label: string
  /** label shown in the tooltip ("Today, 13:00") */
  tooltipLabel: string
  jobs: number
}

function formatHour(ts: number): string {
  return new Date(ts).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function formatTooltipLabel(ts: number): string {
  const d = new Date(ts)
  const now = new Date()
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  const time = d.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  if (sameDay) return `Today, ${time}`
  return `${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}, ${time}`
}

export function JobActivityArea({ buckets }: JobActivityAreaProps) {
  const rows = useMemo<Row[]>(() => {
    return buckets.map((b) => {
      // hour_start is a UTC ISO string from the backend; Date parses it as UTC
      // and toLocaleTimeString renders in the viewer's local timezone.
      const ts = Date.parse(b.hour_start)
      return {
        label: formatHour(ts),
        tooltipLabel: formatTooltipLabel(ts),
        jobs: b.count,
      }
    })
  }, [buckets])

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={rows}
          margin={{ top: 8, right: 16, left: 4, bottom: 4 }}
        >
          <defs>
            <linearGradient id="job-activity-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.45} />
              <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid
            stroke="hsl(var(--border))"
            strokeDasharray="3 3"
            vertical={false}
          />
          <XAxis
            dataKey="label"
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            interval={Math.max(1, Math.floor(rows.length / 6))}
            minTickGap={20}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={28}
          />
          <Tooltip
            cursor={{ stroke: 'hsl(var(--primary))', strokeWidth: 1, strokeDasharray: '3 3' }}
            content={
              <ChartTooltip
                hideIndicator
                titleFormatter={(label) => {
                  const found = rows.find((b) => b.label === label)
                  return found?.tooltipLabel ?? String(label ?? '')
                }}
                valueFormatter={(v) =>
                  `${v.toLocaleString()} job${v === 1 ? '' : 's'}`
                }
              />
            }
          />
          <Area
            type="monotone"
            dataKey="jobs"
            name="Jobs"
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            fill="url(#job-activity-fill)"
            isAnimationActive
            animationDuration={500}
            activeDot={{
              r: 4,
              stroke: 'hsl(var(--background))',
              strokeWidth: 2,
              fill: 'hsl(var(--primary))',
            }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

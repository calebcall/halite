import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { KeyStatus } from '@/features/keys/api'
import { ChartTooltip } from './chart-tooltip'

interface KeyStatusBarProps {
  keys: ReadonlyArray<{ status: KeyStatus }>
}

const STATUS_ORDER: KeyStatus[] = ['accepted', 'pending', 'rejected', 'denied']
const STATUS_LABEL: Record<KeyStatus, string> = {
  accepted: 'Accepted',
  pending: 'Pending',
  rejected: 'Rejected',
  denied: 'Denied',
}

function colorFor(status: KeyStatus): string {
  switch (status) {
    case 'accepted':
      return 'hsl(var(--success))'
    case 'pending':
      return 'hsl(var(--warning))'
    case 'rejected':
    case 'denied':
      return 'hsl(var(--destructive))'
  }
}

export function KeyStatusBar({ keys }: KeyStatusBarProps) {
  const data = useMemo(() => {
    const counts = new Map<KeyStatus, number>()
    for (const k of keys) counts.set(k.status, (counts.get(k.status) ?? 0) + 1)
    return STATUS_ORDER.map((status) => ({
      status,
      label: STATUS_LABEL[status],
      value: counts.get(status) ?? 0,
      fill: colorFor(status),
    }))
  }, [keys])

  const max = useMemo(
    () => Math.max(1, ...data.map((d) => d.value)),
    [data],
  )

  return (
    <div className="h-44 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 0, right: 32, bottom: 0, left: 8 }}
          barCategoryGap={8}
        >
          <XAxis
            type="number"
            hide
            domain={[0, max]}
          />
          <YAxis
            dataKey="label"
            type="category"
            tickLine={false}
            axisLine={false}
            width={72}
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
          />
          <Tooltip
            cursor={{ fill: 'hsl(var(--accent))', opacity: 0.5 }}
            content={
              <ChartTooltip
                hideIndicator
                valueFormatter={(v) =>
                  `${v.toLocaleString()} key${v === 1 ? '' : 's'}`
                }
              />
            }
          />
          <Bar
            dataKey="value"
            name="Keys"
            radius={[4, 4, 4, 4]}
            isAnimationActive
            animationDuration={500}
            barSize={14}
            background={{ fill: 'hsl(var(--muted))', radius: 4 }}
          >
            {data.map((d) => (
              <Cell key={d.status} fill={d.fill} />
            ))}
            <LabelList
              dataKey="value"
              position="right"
              offset={8}
              fill="hsl(var(--foreground))"
              fontSize={11}
              formatter={(v: unknown) =>
                typeof v === 'number' ? v.toLocaleString() : String(v ?? '')
              }
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

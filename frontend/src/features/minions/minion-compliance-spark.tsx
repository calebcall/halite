import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { ChartTooltip } from '@/features/overview/chart-tooltip'

import { useMinionCompliance } from './use-minion-runs'


export function MinionComplianceSpark({ minionId }: { minionId: string }) {
  const { data, isError, isLoading } = useMinionCompliance(minionId, 30)
  if (isLoading) {
    return <div aria-hidden className="h-full animate-pulse rounded bg-muted/40" />
  }
  if (isError) {
    return <p className="text-xs text-destructive">Couldn&apos;t load.</p>
  }
  const points = (data?.buckets ?? []).map((b) => ({
    changed: b.change_count,
    fail: b.fail_count,
    pass: b.pass_count,
    t: new Date(b.completed_at).toLocaleString(undefined, {
      day: 'numeric',
      hour: 'numeric',
      month: 'short',
    }),
  }))
  if (points.length === 0) {
    return <p className="text-xs text-muted-foreground">No runs yet.</p>
  }
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={points} margin={{ bottom: 0, left: 0, right: 4, top: 4 }}>
        <XAxis dataKey="t" hide />
        <YAxis hide />
        <Tooltip content={<ChartTooltip />} />
        <Area
          dataKey="pass"
          fill="hsl(var(--success))"
          fillOpacity={0.3}
          stackId="1"
          stroke="hsl(var(--success))"
          type="monotone"
        />
        <Area
          dataKey="changed"
          fill="hsl(var(--warning))"
          fillOpacity={0.3}
          stackId="1"
          stroke="hsl(var(--warning))"
          type="monotone"
        />
        <Area
          dataKey="fail"
          fill="hsl(var(--destructive))"
          fillOpacity={0.4}
          stackId="1"
          stroke="hsl(var(--destructive))"
          type="monotone"
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

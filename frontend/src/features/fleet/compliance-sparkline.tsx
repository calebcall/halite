import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { ChartTooltip } from '@/features/overview/chart-tooltip'

import { useFleetCompliance } from './use-fleet'

export function ComplianceSparkline() {
  const { data, isLoading, isError } = useFleetCompliance(30)
  const points = (data?.buckets ?? []).map((b) => ({
    t: new Date(b.bucketed_at).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
    }),
    pass: b.pass_count,
    changed: b.change_count,
    fail: b.fail_count,
  }))

  return (
    <section className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <header>
        <h2 className="text-sm font-semibold tracking-tight">Compliance trend</h2>
        <p className="text-xs text-muted-foreground">
          Last 30 highstate runs, fleet-aggregated.
        </p>
      </header>
      <div className="mt-3 h-32">
        {isLoading && <div aria-hidden className="h-full animate-pulse rounded bg-muted/40" />}
        {isError && (
          <p className="text-sm text-destructive">Couldn&apos;t load compliance.</p>
        )}
        {!isLoading && !isError && points.length === 0 && (
          <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
            No runs ingested yet.
          </p>
        )}
        {!isLoading && !isError && points.length > 0 && (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <XAxis dataKey="t" hide />
              <YAxis hide />
              <Tooltip content={<ChartTooltip />} />
              <Area
                type="monotone"
                dataKey="pass"
                stackId="1"
                stroke="hsl(var(--success))"
                fill="hsl(var(--success))"
                fillOpacity={0.3}
              />
              <Area
                type="monotone"
                dataKey="changed"
                stackId="1"
                stroke="hsl(var(--warning))"
                fill="hsl(var(--warning))"
                fillOpacity={0.3}
              />
              <Area
                type="monotone"
                dataKey="fail"
                stackId="1"
                stroke="hsl(var(--destructive))"
                fill="hsl(var(--destructive))"
                fillOpacity={0.4}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  )
}

import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { ChartTooltip } from '@/features/overview/chart-tooltip'

import { useFleetTopFailures } from './use-fleet'

export function TopFailuresChart() {
  const { data, isError, isLoading } = useFleetTopFailures(10)
  const rows = (data?.failures ?? []).map((f) => ({
    count: f.failure_count,
    label: `${f.fun}: ${f.state_id}`,
    name: f.name,
  }))

  return (
    <section className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <header>
        <h2 className="text-sm font-semibold tracking-tight">Top failed states</h2>
        <p className="text-xs text-muted-foreground">
          States failing the most minions across the latest runs.
        </p>
      </header>

      <div className="mt-3 h-40">
        {isLoading && <div aria-hidden className="h-full animate-pulse rounded bg-muted/40" />}
        {isError && (
          <p className="text-sm text-destructive">Couldn&apos;t load failures.</p>
        )}
        {!isLoading && !isError && rows.length === 0 && (
          <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
            No failures across the fleet right now.
          </p>
        )}
        {!isLoading && !isError && rows.length > 0 && (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={rows}
              layout="vertical"
              margin={{ bottom: 0, left: 8, right: 16, top: 4 }}
            >
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="label"
                width={180}
                tick={{ fontSize: 11 }}
              />
              <Tooltip content={<ChartTooltip />} />
              <Bar
                dataKey="count"
                fill="hsl(var(--destructive))"
                name="Failures"
                radius={[0, 4, 4, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  )
}

import { Link } from '@tanstack/react-router'

import { ChartCard } from '@/features/overview/chart-card'

import { useActivityList } from './use-activity'
import { ActivityRow } from './activity-row'

interface RecentActivityCardProps {
  className?: string
}

export function RecentActivityCard({ className }: RecentActivityCardProps = {}) {
  // Heartbeat: total events in the last hour (all events, including routine).
  // Limit 1 keeps the payload tiny — we only read `total`. This re-fetches
  // live because the global stream invalidates ['activity'].
  const heartbeat = useActivityList({
    since_minutes: 60,
    hide_routine: false,
    limit: 1,
  })
  const lastHour = heartbeat.data?.total ?? 0

  // Notable recent events: all returns (including routine successes) + key/minion
  // events. Excludes only job.new dispatches — routine successes are intentionally
  // included here so the widget reflects real fleet activity.
  const { data } = useActivityList({ hide_dispatch: true, limit: 6 })
  const events = data?.events ?? []

  return (
    <ChartCard title="Recent activity" description="Live fleet events" className={className}>
      <div className="flex items-center gap-2 px-3 pb-3 text-sm">
        <span className="relative flex size-2 shrink-0">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-success/70" />
          <span className="relative inline-flex size-2 rounded-full bg-success" />
        </span>
        <span className="font-semibold tabular-nums text-foreground">{lastHour}</span>
        <span className="text-muted-foreground">events · last hour</span>
      </div>

      <ul className="flex flex-col px-3">
        {events.length === 0 ? (
          <li className="py-2 text-sm text-muted-foreground">No notable activity.</li>
        ) : (
          events.map((e) => <ActivityRow key={e.id} event={e} compact />)
        )}
      </ul>

      <Link
        to="/activity"
        className="mt-3 inline-block px-3 text-xs text-primary hover:underline"
      >
        View all →
      </Link>
    </ChartCard>
  )
}

import { Link } from '@tanstack/react-router'

import { ChartCard } from '@/features/overview/chart-card'

import { useActivityList } from './use-activity'

interface RecentActivityCardProps {
  className?: string
}

export function RecentActivityCard({ className }: RecentActivityCardProps = {}) {
  const { data } = useActivityList({ limit: 8 })
  const events = data?.events ?? []
  return (
    <ChartCard title="Recent activity" description="Live fleet events" className={className}>
      <ul className="flex flex-col gap-1.5 px-3">
        {events.length === 0 ? (
          <li className="text-sm text-muted-foreground">No activity yet.</li>
        ) : (
          events.map((e) => (
            <li key={e.id} className="flex items-center gap-2 text-sm">
              <span className="shrink-0 text-[10px] uppercase tracking-wide text-muted-foreground">
                {e.category}
              </span>
              <span className="truncate">{e.summary}</span>
            </li>
          ))
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

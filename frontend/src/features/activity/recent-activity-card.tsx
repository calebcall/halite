import { Link } from '@tanstack/react-router'

import { ChartCard } from '@/features/overview/chart-card'

import { useActivityList } from './use-activity'
import { useWidgetConfig } from './use-widget-config'
import { ActivityRow } from './activity-row'

function formatWindow(min: number): string {
  if (min === 60) return 'last hour'
  if (min % 60 === 0) return `last ${min / 60} h`
  return `last ${min} min`
}

interface RecentActivityCardProps {
  className?: string
}

// Sensible defaults applied while the widget config query is loading (or if it
// errors) so the widget always renders with the historical behaviour:
// hide dispatches, show all categories, 6 events, 60-minute heartbeat window.
const FALLBACK = {
  widget_hide_dispatch: true,
  widget_hide_routine: false,
  widget_show_jobs: true,
  widget_show_keys: true,
  widget_show_minions: true,
  widget_event_count: 6,
  widget_heartbeat_minutes: 60,
}

export function RecentActivityCard({ className }: RecentActivityCardProps = {}) {
  const { data: cfgData } = useWidgetConfig()
  const cfg = cfgData ?? FALLBACK

  // Build a categories CSV from the show_* toggles. When all three are on we
  // send `undefined` (no filter) so the backend returns every category.
  const selected = [
    cfg.widget_show_jobs && 'job',
    cfg.widget_show_keys && 'key',
    cfg.widget_show_minions && 'minion',
  ].filter((c): c is string => Boolean(c))
  const categories = selected.length === 3 ? undefined : selected.join(',')

  // Heartbeat: total events in the configured window (all events, including
  // routine). Limit 1 keeps the payload tiny — we only read `total`. This
  // re-fetches live because the global stream invalidates ['activity'].
  const heartbeat = useActivityList({
    since_minutes: cfg.widget_heartbeat_minutes,
    hide_routine: false,
    limit: 1,
  })
  const lastHour = heartbeat.data?.total ?? 0

  // Notable recent events. Categories + dispatch/routine filtering come from
  // the admin-configurable widget settings.
  const { data } = useActivityList({
    hide_dispatch: cfg.widget_hide_dispatch,
    hide_routine: cfg.widget_hide_routine,
    categories,
    limit: cfg.widget_event_count,
  })
  // When zero categories are selected, show nothing — avoid the empty-string
  // `categories=''` case where the backend falls back to returning all events.
  const events = selected.length === 0 ? [] : (data?.events ?? [])

  return (
    <ChartCard title="Recent activity" description="Live fleet events" className={className}>
      <div className="flex items-center gap-2 px-3 pb-3 text-sm">
        <span className="relative flex size-2 shrink-0">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-success/70" />
          <span className="relative inline-flex size-2 rounded-full bg-success" />
        </span>
        <span className="font-semibold tabular-nums text-foreground">{lastHour}</span>
        <span className="text-muted-foreground">events · {formatWindow(cfg.widget_heartbeat_minutes)}</span>
      </div>

      <ul className="flex flex-col px-3">
        {selected.length === 0 ? (
          <li className="py-2 text-sm text-muted-foreground">No event categories enabled.</li>
        ) : events.length === 0 ? (
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

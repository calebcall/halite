// frontend/src/features/activity/activity-row.tsx
import {
  AlertTriangle,
  CheckCircle2,
  GitCommit,
  KeyRound,
  Play,
  Server,
  XCircle,
  type LucideIcon,
} from 'lucide-react'

import { Badge, type BadgeProps } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

import type { ActivityEventOut } from './api'

/** Compact relative-time formatter for the activity feed. */
export function timeAgo(iso: string): string {
  const d = new Date(iso)
  const diff = Date.now() - d.getTime()
  const sec = Math.round(diff / 1000)
  if (sec < 5) return 'now'
  if (sec < 60) return `${sec}s ago`
  const min = Math.round(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.round(min / 60)
  if (hr < 24) return `${hr}h ago`
  return `${Math.round(hr / 24)}d ago`
}

type BadgeVariant = NonNullable<BadgeProps['variant']>

interface ActivityVisual {
  icon: LucideIcon
  /** Tailwind text-color token for the leading icon. */
  iconClass: string
  badge: string
  badgeVariant: BadgeVariant
}

/**
 * Derives the icon, color, and outcome badge for an activity event.
 * Shared by the full activity page and the compact overview widget so the
 * mapping stays consistent in one place.
 */
export function activityVisual(e: ActivityEventOut): ActivityVisual {
  switch (e.event_type) {
    case 'job.ret':
      if (e.success === false) {
        return {
          icon: XCircle,
          iconClass: 'text-destructive',
          badge: 'Failed',
          badgeVariant: 'destructive',
        }
      }
      if (e.changed === true) {
        return {
          icon: GitCommit,
          iconClass: 'text-warning',
          badge: 'Changes',
          badgeVariant: 'warning',
        }
      }
      return {
        icon: CheckCircle2,
        iconClass: 'text-muted-foreground',
        badge: 'OK',
        badgeVariant: 'info',
      }
    case 'job.new':
      return {
        icon: Play,
        iconClass: 'text-primary',
        badge: 'Dispatched',
        badgeVariant: 'default',
      }
    case 'key.accept':
      return {
        icon: KeyRound,
        iconClass: 'text-success',
        badge: 'Accepted',
        badgeVariant: 'success',
      }
    case 'key.reject':
      return {
        icon: KeyRound,
        iconClass: 'text-destructive',
        badge: 'Rejected',
        badgeVariant: 'destructive',
      }
    case 'key.pend':
      return {
        icon: KeyRound,
        iconClass: 'text-warning',
        badge: 'Pending',
        badgeVariant: 'warning',
      }
    case 'key.delete':
      return {
        icon: KeyRound,
        iconClass: 'text-muted-foreground',
        badge: 'Deleted',
        badgeVariant: 'info',
      }
    case 'minion.start':
      return {
        icon: Server,
        iconClass: 'text-success',
        badge: 'Online',
        badgeVariant: 'success',
      }
    default:
      return {
        icon: AlertTriangle,
        iconClass: 'text-muted-foreground',
        badge: e.event_type,
        badgeVariant: 'info',
      }
  }
}

/** Secondary label: the function name, or a humanized fallback. */
function secondaryLabel(e: ActivityEventOut): string {
  if (e.fun) return e.fun
  return e.event_type
}

interface ActivityRowProps {
  event: ActivityEventOut
  /** Compact variant for the overview widget. */
  compact?: boolean
}

export function ActivityRow({ event, compact = false }: ActivityRowProps) {
  const visual = activityVisual(event)
  const Icon = visual.icon

  if (compact) {
    return (
      <li className="flex items-center gap-2.5 py-1.5 text-sm">
        <Icon className={cn('size-4 shrink-0', visual.iconClass)} />
        <span className="min-w-0 flex-1 truncate">
          <span className="font-medium text-foreground">
            {event.minion_id ?? 'fleet'}
          </span>
          <span className="ml-1.5 text-xs text-muted-foreground">
            {secondaryLabel(event)}
          </span>
        </span>
        <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
          {timeAgo(event.ts)}
        </span>
      </li>
    )
  }

  return (
    <li className="flex items-center gap-3 border-b border-border/50 px-4 py-3 last:border-b-0 hover:bg-accent/40">
      <span
        className={cn(
          'flex size-8 shrink-0 items-center justify-center rounded-md bg-muted/60',
          visual.iconClass,
        )}
      >
        <Icon className="size-4" />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <span className="truncate font-semibold text-foreground">
            {event.minion_id ?? 'fleet'}
          </span>
          <span className="truncate font-mono text-xs text-muted-foreground">
            {secondaryLabel(event)}
          </span>
        </div>
        <span className="truncate text-xs text-muted-foreground">
          {event.summary}
        </span>
      </div>
      <Badge variant={visual.badgeVariant} className="shrink-0">
        {visual.badge}
      </Badge>
      <span
        className="w-20 shrink-0 text-right text-xs tabular-nums text-muted-foreground"
        title={new Date(event.ts).toLocaleString()}
      >
        {timeAgo(event.ts)}
      </span>
    </li>
  )
}

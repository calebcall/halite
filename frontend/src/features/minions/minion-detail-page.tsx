// frontend/src/features/minions/minion-detail-page.tsx
import { AlertTriangle, ArrowLeft, Clock, Loader2 } from 'lucide-react'
import { Link, useParams } from '@tanstack/react-router'

import { cn } from '@/lib/utils'
import { ApiError, errorDetail } from '@/shared/api/client'
import { MustChangePassword } from '@/features/auth/guards'

import { MinionGrainExplorer } from './minion-grain-explorer'
import { MinionQuickActions } from './minion-quick-actions'
import { MinionRunsTable } from './minion-runs-table'
import { MinionStatusCards } from './minion-status-cards'
import { MinionStatusHeader } from './minion-status-header'
import { useMinion } from './use-minions'

function formatRelativeTime(d: Date): string {
  const diff = Date.now() - d.getTime()
  const sec = Math.round(diff / 1000)
  if (sec < 60) return 'just now'
  const min = Math.round(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.round(min / 60)
  if (hr < 24) return `${hr}h ago`
  return `${Math.round(hr / 24)}d ago`
}

export function MinionDetailPage() {
  return (
    <MustChangePassword>
      <MinionDetailPageInner />
    </MustChangePassword>
  )
}

function MinionDetailPageInner() {
  const { minionId } = useParams({ from: '/app/minions/$minionId' })
  const { data, isPending, error } = useMinion(minionId)
  const detail = errorDetail(error)

  if (error instanceof ApiError && error.status === 404) {
    return <NotFoundPanel minionId={minionId} />
  }
  if (error instanceof ApiError && error.isForbidden) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        You don&apos;t have permission to view minions.
      </div>
    )
  }
  if (error instanceof ApiError && error.status === 503) {
    return (
      <div className="rounded-md border border-warning/40 bg-warning/10 p-6 text-sm text-foreground">
        <p>Salt-API is not configured.</p>
        {detail && <p className="mt-2 font-mono text-xs">{detail}</p>}
      </div>
    )
  }
  if (error instanceof ApiError && error.status === 502) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        <p>Salt-API responded with an error.</p>
        {detail && <p className="mt-2 font-mono text-xs">{detail}</p>}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <Link to="/minions" className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:underline">
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to minions
      </Link>

      {isPending && (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      )}

      {data && (
        <>
          <MinionStatusHeader minion={data} />

          {data.last_refreshed_at && (
            <span
              className={cn(
                'inline-flex items-center gap-1.5 text-xs',
                data.is_stale ? 'text-warning' : 'text-muted-foreground',
              )}
              title={new Date(data.last_refreshed_at).toLocaleString()}
            >
              {data.is_stale ? (
                <AlertTriangle className="size-3" />
              ) : (
                <Clock className="size-3" />
              )}
              Updated {formatRelativeTime(new Date(data.last_refreshed_at))}
              {data.is_stale && ' — data is stale'}
            </span>
          )}

          <MinionQuickActions minionId={data.id} />
          <MinionStatusCards minionId={data.id} />
          <MinionRunsTable minionId={data.id} />
          <MinionGrainExplorer
            grains={(data.grains as Record<string, unknown> | null) ?? null}
          />
        </>
      )}
    </div>
  )
}

function NotFoundPanel({ minionId }: { minionId: string }) {
  return (
    <div className="flex flex-col gap-4">
      <Link to="/minions" className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:underline">
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to minions
      </Link>
      <div className="rounded-md border p-6 text-sm">
        <p className="font-medium">Minion not found</p>
        <p className="text-muted-foreground">
          No minion named <span className="font-mono">{minionId}</span> is known to the master in
          any state.
        </p>
      </div>
    </div>
  )
}

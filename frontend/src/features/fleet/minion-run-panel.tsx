// frontend/src/features/fleet/minion-run-panel.tsx
import { Link } from '@tanstack/react-router'
import { ExternalLink, Loader2 } from 'lucide-react'

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from '@/components/ui/sheet'
import { parseHighstate } from '@/features/jobs/highstate/parse'
import type { components } from '@/shared/api/types.gen'

import { useFleetRun } from './use-fleet'

type Minion = components['schemas']['MinionHealthOut']

export function MinionRunPanel({
  minion,
  onOpenChange,
  open,
}: {
  minion: Minion | null
  onOpenChange: (open: boolean) => void
  open: boolean
}) {
  const runId = minion?.run_id ?? null
  const { data, isError, isLoading } = useFleetRun(open ? runId : null)

  const parsed = data?.raw_result
    ? parseHighstate(data.raw_result as Record<string, unknown>)
    : null

  const summary = parsed
    ? {
        changed: parsed.filter(
          (s) =>
            s.result !== false &&
            s.changes !== null &&
            typeof s.changes === 'object' &&
            Object.keys(s.changes as object).length > 0,
        ).length,
        failed: parsed.filter((s) => s.result === false).length,
        total: parsed.length,
      }
    : null

  return (
    <Sheet onOpenChange={onOpenChange} open={open}>
      <SheetContent className="w-full sm:max-w-3xl" side="right">
        <div className="px-6 pb-2 pt-6">
          <SheetTitle>{minion?.minion_id ?? 'Minion'}</SheetTitle>
          <SheetDescription>
            Most recent highstate run
            {data?.completed_at && (
              <> &middot; {new Date(data.completed_at).toLocaleString()}</>
            )}
          </SheetDescription>
        </div>

        <div
          className="mt-2 space-y-3 overflow-y-auto px-6 pr-5"
          style={{ maxHeight: 'calc(100vh - 8rem)' }}
        >
          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Loading run&hellip;
            </div>
          )}

          {isError && (
            <p className="text-sm text-destructive">
              Couldn&apos;t load this run.
            </p>
          )}

          {data?.blocked && (
            <p className="text-sm text-amber-600 dark:text-amber-400">
              Minion was blocked or didn&apos;t respond during this run.
            </p>
          )}

          {summary && (
            <p className="text-xs text-muted-foreground">
              {summary.total} states &middot;{' '}
              {summary.total - summary.failed - summary.changed} pass &middot;{' '}
              {summary.changed} changed &middot; {summary.failed} failed
            </p>
          )}

          {parsed && (
            <ul className="space-y-1.5 text-sm">
              {parsed.map((s, idx) => (
                <li
                  className={
                    s.result === false
                      ? 'rounded border border-destructive/30 bg-destructive/10 p-2'
                      : 'rounded border border-border p-2'
                  }
                  key={idx}
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono">
                      {s.module}.{s.fun}
                    </span>
                    <span className="text-muted-foreground">{s.stateId}</span>
                  </div>
                  {s.comment && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {s.comment}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}

          {minion && (
            <div className="pt-2">
              <Link
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                params={{ minionId: minion.minion_id }}
                to="/minions/$minionId"
              >
                Open full minion view <ExternalLink className="size-3" />
              </Link>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

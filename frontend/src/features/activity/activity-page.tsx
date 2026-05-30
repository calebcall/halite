// frontend/src/features/activity/activity-page.tsx
import { useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'

import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { MustChangePassword } from '@/features/auth/guards'
import { useHasPerm } from '@/features/auth/use-has-perm'
import { useActivityList } from './use-activity'
import { ActivityRow } from './activity-row'
import type { ActivityFilter } from './api'

export function ActivityPage() {
  return (
    <MustChangePassword>
      <ActivityPageInner />
    </MustChangePassword>
  )
}

function ActivityPageInner() {
  const canJob = useHasPerm('view', 'job:*')
  const canKey = useHasPerm('view', 'key:*')
  const canMinion = useHasPerm('view', 'minion:*')
  const canViewAny = canJob || canKey || canMinion

  const [category, setCategory] = useState('')
  const [search, setSearch] = useState('')
  // Default OFF → hide routine successful-no-change returns (the constant
  // state.highstate drip). Toggling on surfaces them.
  const [showRoutine, setShowRoutine] = useState(false)

  const filter: ActivityFilter = useMemo(
    () => ({
      category: category || undefined,
      search: search || undefined,
      hide_routine: !showRoutine,
      limit: 200,
    }),
    [category, search, showRoutine],
  )

  const { data, isPending, error } = useActivityList(filter)

  if (!canViewAny) {
    return (
      <p className="text-sm text-muted-foreground">You don&apos;t have access to any activity.</p>
    )
  }

  if (error) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        Failed to load activity.
      </div>
    )
  }

  const events = data?.events ?? []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Activity</h2>
          <p className="text-sm text-muted-foreground">
            Recent fleet events. Updates live via the event stream.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
          aria-label="Filter by category"
        >
          <option value="">All</option>
          <option value="job">Jobs</option>
          <option value="key">Keys</option>
          <option value="minion">Minions</option>
        </select>

        <Input
          type="search"
          placeholder="Search events…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-md"
        />

        <label className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
          <Switch
            checked={showRoutine}
            onCheckedChange={setShowRoutine}
            aria-label="Show routine successes"
          />
          Show routine successes
        </label>
      </div>

      <div className="rounded-md border">
        {isPending && (
          <div className="flex h-24 items-center justify-center text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
          </div>
        )}
        {!isPending && events.length === 0 && (
          <div className="flex h-24 items-center justify-center text-sm text-muted-foreground">
            No activity events found.
          </div>
        )}
        {!isPending && events.length > 0 && (
          <ul className="flex flex-col">
            {events.map((e) => (
              <ActivityRow key={e.id} event={e} />
            ))}
          </ul>
        )}
      </div>

      {data && events.length > 0 && (
        <p className="text-sm text-muted-foreground">
          {data.total} event{data.total === 1 ? '' : 's'}
          {events.length < data.total ? ` (showing ${events.length})` : ''}.
        </p>
      )}
    </div>
  )
}

// frontend/src/features/activity/activity-page.tsx
import { useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { MustChangePassword } from '@/features/auth/guards'
import { useHasPerm } from '@/features/auth/use-has-perm'
import { useActivityList } from './use-activity'
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

  const filter: ActivityFilter = useMemo(
    () => ({ category: category || undefined, search: search || undefined, limit: 200 }),
    [category, search],
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

      <div className="flex flex-wrap gap-3">
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
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-48">Time</TableHead>
              <TableHead className="w-24">Category</TableHead>
              <TableHead>Event</TableHead>
              <TableHead>Minion</TableHead>
              <TableHead>Summary</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isPending && (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                  <Loader2 className="mx-auto h-4 w-4 animate-spin" />
                </TableCell>
              </TableRow>
            )}
            {!isPending && (!data || data.events.length === 0) && (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                  No activity events found.
                </TableCell>
              </TableRow>
            )}
            {data?.events.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="text-xs text-muted-foreground">
                  {new Date(e.ts).toLocaleString()}
                </TableCell>
                <TableCell>
                  <CategoryBadge category={e.category} />
                </TableCell>
                <TableCell className="font-mono text-xs">{e.event_type}</TableCell>
                <TableCell className="font-mono text-xs">{e.minion_id ?? '—'}</TableCell>
                <TableCell className="text-xs">{e.summary}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {data && data.events.length > 0 && (
        <p className="text-sm text-muted-foreground">
          {data.total} event{data.total === 1 ? '' : 's'}{data.events.length < data.total ? ` (showing ${data.events.length})` : ''}.
        </p>
      )}
    </div>
  )
}

function CategoryBadge({ category }: { category: string }) {
  if (category === 'job') return <Badge variant="info">job</Badge>
  if (category === 'key') return <Badge variant="warning">key</Badge>
  if (category === 'minion') return <Badge variant="secondary">minion</Badge>
  return <Badge variant="outline">{category}</Badge>
}

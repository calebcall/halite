// frontend/src/features/audit/audit-viewer-page.tsx
import { Loader2 } from 'lucide-react'
import { useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ApiError } from '@/shared/api/client'
import { MustChangePassword } from '@/features/auth/guards'
import type { AuditFilter, Decision } from './api'
import { useAuditList } from './use-audit'

const PAGE_SIZE = 50

export function AuditViewerPage() {
  return (
    <MustChangePassword>
      <AuditViewerPageInner />
    </MustChangePassword>
  )
}

function AuditViewerPageInner() {
  const [action, setAction] = useState('')
  const [decision, setDecision] = useState<Decision | ''>('')
  const [since, setSince] = useState('')
  const [until, setUntil] = useState('')
  const [page, setPage] = useState(0)

  const filter = useMemo<AuditFilter>(
    () => ({
      action: action.trim() || undefined,
      decision: decision || undefined,
      since: since ? new Date(since).toISOString() : undefined,
      until: until ? new Date(until).toISOString() : undefined,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    }),
    [action, decision, since, until, page],
  )

  const { data, isPending, error } = useAuditList(filter)

  if (error instanceof ApiError && error.isForbidden) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        You don&apos;t have permission to view the audit log.
      </div>
    )
  }

  function resetFilters() {
    setAction('')
    setDecision('')
    setSince('')
    setUntil('')
    setPage(0)
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Audit log</h2>
        <p className="text-sm text-muted-foreground">
          Every mutation and every denied permission check.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 rounded-md border p-3 md:grid-cols-5">
        <div className="space-y-1">
          <Label htmlFor="filter-action" className="text-xs">Action</Label>
          <Input
            id="filter-action"
            placeholder="user.create"
            value={action}
            onChange={(e) => { setPage(0); setAction(e.target.value) }}
            autoComplete="off"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="filter-decision" className="text-xs">Decision</Label>
          <select
            id="filter-decision"
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
            value={decision}
            onChange={(e) => { setPage(0); setDecision(e.target.value as Decision | '') }}
          >
            <option value="">Any</option>
            <option value="allow">Allow</option>
            <option value="deny">Deny</option>
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="filter-since" className="text-xs">Since</Label>
          <Input
            id="filter-since"
            type="datetime-local"
            value={since}
            onChange={(e) => { setPage(0); setSince(e.target.value) }}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="filter-until" className="text-xs">Until</Label>
          <Input
            id="filter-until"
            type="datetime-local"
            value={until}
            onChange={(e) => { setPage(0); setUntil(e.target.value) }}
          />
        </div>
        <div className="flex items-end">
          <Button variant="outline" size="sm" onClick={resetFilters} className="w-full">
            Clear filters
          </Button>
        </div>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-44">When</TableHead>
              <TableHead className="w-32">User</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Resource</TableHead>
              <TableHead className="w-20">Decision</TableHead>
              <TableHead className="w-16 text-right">Code</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isPending && (
              <TableRow>
                <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                  <Loader2 className="mx-auto h-4 w-4 animate-spin" />
                </TableCell>
              </TableRow>
            )}
            {!isPending && data && data.entries.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                  No audit entries match the current filters.
                </TableCell>
              </TableRow>
            )}
            {data?.entries.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="font-mono text-xs">{formatTimestamp(e.at)}</TableCell>
                <TableCell className="font-mono text-xs">
                  {e.user_id ? e.user_id.slice(0, 8) : <span className="text-muted-foreground">—</span>}
                </TableCell>
                <TableCell className="font-medium">{e.action}</TableCell>
                <TableCell className="font-mono text-xs">{e.resource}</TableCell>
                <TableCell>
                  <span
                    className={
                      e.decision === 'allow'
                        ? 'rounded bg-emerald-100 px-1.5 py-0.5 text-xs font-medium text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200'
                        : 'rounded bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-900 dark:bg-red-950/40 dark:text-red-200'
                    }
                  >
                    {e.decision}
                  </span>
                </TableCell>
                <TableCell className="text-right font-mono text-xs">{e.result_code}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {data && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {data.total === 0
              ? 'No matching entries'
              : `Showing ${page * PAGE_SIZE + 1}-${Math.min((page + 1) * PAGE_SIZE, data.total)} of ${data.total}`}
          </span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={(page + 1) * PAGE_SIZE >= data.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

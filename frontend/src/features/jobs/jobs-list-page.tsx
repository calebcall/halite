// frontend/src/features/jobs/jobs-list-page.tsx
import { useMemo, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { Loader2, Square } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ApiError, errorDetail } from '@/shared/api/client'
import { MustChangePassword } from '@/features/auth/guards'
import { useHasPerm } from '@/features/auth/use-has-perm'
import { KillByJidDialog } from './kill-by-jid-dialog'
import { useJobsList } from './use-jobs'

export function JobsListPage() {
  return (
    <MustChangePassword>
      <JobsListPageInner />
    </MustChangePassword>
  )
}

function JobsListPageInner() {
  const { data, isPending, error } = useJobsList()
  const detail = errorDetail(error)

  const canKill = useHasPerm('kill', 'job:*')
  const [filter, setFilter] = useState('')
  const [killByJidOpen, setKillByJidOpen] = useState(false)

  const filteredJobs = useMemo(() => {
    if (!data) return []
    const q = filter.trim().toLowerCase()
    if (!q) return data.jobs
    return data.jobs.filter((j) =>
      j.jid.toLowerCase().includes(q) ||
      j.function.toLowerCase().includes(q) ||
      (j.target || '').toLowerCase().includes(q) ||
      (j.user || '').toLowerCase().includes(q),
    )
  }, [data, filter])

  if (error instanceof ApiError && error.isForbidden) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        You don&apos;t have permission to view jobs.
      </div>
    )
  }
  if (error instanceof ApiError && error.status === 503) {
    return (
      <div className="rounded-md border border-warning/40 bg-warning/10 p-6 text-sm text-foreground">
        <p>Salt-API is not configured. Set <code>SALT_API_URL</code>, <code>SALT_API_USERNAME</code>, and <code>SALT_API_PASSWORD</code> in your <code>.env</code> and restart the stack.</p>
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
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Jobs</h2>
          <p className="text-sm text-muted-foreground">
            Recent salt jobs from the master cache. Refreshes every 30 seconds.
          </p>
        </div>
        {canKill && (
          <Button
            variant="outline"
            size="sm"
            className="text-destructive hover:text-destructive"
            onClick={() => setKillByJidOpen(true)}
          >
            <Square className="mr-2 h-4 w-4 fill-current" />
            Kill by JID
          </Button>
        )}
      </div>

      <Input
        type="search"
        placeholder="Filter by jid, function, target, or user…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="max-w-md"
      />

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-56">JID</TableHead>
              <TableHead>Function</TableHead>
              <TableHead>Target</TableHead>
              <TableHead className="w-24">Status</TableHead>
              <TableHead>User</TableHead>
              <TableHead className="w-48">Started</TableHead>
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
            {!isPending && data && data.jobs.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                  No jobs in the master cache.
                </TableCell>
              </TableRow>
            )}
            {filteredJobs.map((j) => (
              <TableRow key={j.jid}>
                <TableCell className="font-mono text-xs">
                  <Link to="/jobs/$jid" params={{ jid: j.jid }} className="block hover:underline">
                    {j.jid}
                  </Link>
                </TableCell>
                <TableCell className="font-mono text-xs">{j.function}</TableCell>
                <TableCell className="font-mono text-xs">{j.target || '—'}</TableCell>
                <TableCell>
                  <JobStatusBadge status={j.status} />
                </TableCell>
                <TableCell className="text-xs">{j.user || '—'}</TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {j.start_time || '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {data && data.jobs.length > 0 && (
        <p className="text-sm text-muted-foreground">
          {filter
            ? `Showing ${filteredJobs.length} of ${data.total} recent job${data.total === 1 ? '' : 's'}.`
            : `${data.total} recent job${data.total === 1 ? '' : 's'}.`}
        </p>
      )}

      <KillByJidDialog open={killByJidOpen} onOpenChange={setKillByJidOpen} />
    </div>
  )
}

function JobStatusBadge({ status }: { status: 'running' | 'complete' }) {
  if (status === 'running') {
    return <Badge variant="warning">running</Badge>
  }
  return <Badge variant="info">complete</Badge>
}

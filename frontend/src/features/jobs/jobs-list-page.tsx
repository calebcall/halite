// frontend/src/features/jobs/jobs-list-page.tsx
import { Link } from '@tanstack/react-router'
import { Loader2 } from 'lucide-react'

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

  if (error instanceof ApiError && error.isForbidden) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        You don&apos;t have permission to view jobs.
      </div>
    )
  }
  if (error instanceof ApiError && error.status === 503) {
    return (
      <div className="rounded-md border border-amber-400/40 bg-amber-50 p-6 text-sm text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
        Salt-API is not configured. Set <code>SALT_API_URL</code>, <code>SALT_API_USERNAME</code>, and <code>SALT_API_PASSWORD</code> in your <code>.env</code> and restart the stack.
      </div>
    )
  }
  if (error instanceof ApiError && error.status === 502) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        Salt-API responded with an error.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Jobs</h2>
        <p className="text-sm text-muted-foreground">
          Recent salt jobs from the master cache. Refreshes every 30 seconds.
        </p>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-56">JID</TableHead>
              <TableHead>Function</TableHead>
              <TableHead>Target</TableHead>
              <TableHead>User</TableHead>
              <TableHead className="w-48">Started</TableHead>
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
            {!isPending && data && data.jobs.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                  No jobs in the master cache.
                </TableCell>
              </TableRow>
            )}
            {data?.jobs.map((j) => (
              <TableRow key={j.jid}>
                <TableCell className="font-mono text-xs">
                  <Link to="/jobs/$jid" params={{ jid: j.jid }} className="block hover:underline">
                    {j.jid}
                  </Link>
                </TableCell>
                <TableCell className="font-mono text-xs">{j.function}</TableCell>
                <TableCell className="font-mono text-xs">{j.target || '—'}</TableCell>
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
          {data.total} recent job{data.total === 1 ? '' : 's'}.
        </p>
      )}
    </div>
  )
}

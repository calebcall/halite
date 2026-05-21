// frontend/src/features/minions/minions-list-page.tsx
import { Loader2, Server } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
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
import { useMinionsList } from './use-minions'

export function MinionsListPage() {
  return (
    <MustChangePassword>
      <MinionsListPageInner />
    </MustChangePassword>
  )
}

function MinionsListPageInner() {
  const { data, isPending, error } = useMinionsList()

  if (error instanceof ApiError && error.isForbidden) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        You don&apos;t have permission to view minions.
      </div>
    )
  }

  if (error instanceof ApiError && error.status === 503) {
    return (
      <div className="rounded-md border border-amber-400/40 bg-amber-50 p-6 text-sm text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
        Salt-API is not configured. Set <code>SALT_API_URL</code>, <code>SALT_API_USERNAME</code>,
        and <code>SALT_API_PASSWORD</code> in your <code>.env</code> and restart the stack.
      </div>
    )
  }

  if (error instanceof ApiError && error.status === 502) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        Salt-API responded with an error. Check the backend logs for details.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Minions</h2>
        <p className="text-sm text-muted-foreground">
          Connected accepted minions. Refreshes every 30 seconds.
        </p>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Minion ID</TableHead>
              <TableHead>IP</TableHead>
              <TableHead className="w-32 text-right">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isPending && (
              <TableRow>
                <TableCell colSpan={3} className="h-24 text-center text-muted-foreground">
                  <Loader2 className="mx-auto h-4 w-4 animate-spin" />
                </TableCell>
              </TableRow>
            )}
            {!isPending && data && data.minions.length === 0 && (
              <TableRow>
                <TableCell colSpan={3} className="h-24 text-center text-muted-foreground">
                  No minions connected.
                </TableCell>
              </TableRow>
            )}
            {data?.minions.map((m) => (
              <TableRow key={m.id}>
                <TableCell className="flex items-center gap-2 font-mono text-xs">
                  <Server className="h-3.5 w-3.5 text-muted-foreground" />
                  {m.id}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {m.ip || <span className="text-muted-foreground">—</span>}
                </TableCell>
                <TableCell className="text-right">
                  <Badge variant="secondary">connected</Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {data && data.minions.length > 0 && (
        <p className="text-sm text-muted-foreground">
          {data.total} minion{data.total === 1 ? '' : 's'} connected.
        </p>
      )}
    </div>
  )
}

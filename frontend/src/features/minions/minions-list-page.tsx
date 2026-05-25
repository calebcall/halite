// frontend/src/features/minions/minions-list-page.tsx
import { Loader2, MoreHorizontal, Server, Terminal } from 'lucide-react'
import { Link, useNavigate } from '@tanstack/react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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
import type { MinionStatus } from './api'
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
  const canRun = useHasPerm('execute', 'salt:*')
  const navigate = useNavigate()
  const detail = errorDetail(error)

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
        <p>Salt-API is not configured. Set <code>SALT_API_URL</code>, <code>SALT_API_USERNAME</code>,
        and <code>SALT_API_PASSWORD</code> in your <code>.env</code> and restart the stack.</p>
        {detail && <p className="mt-2 font-mono text-xs">{detail}</p>}
      </div>
    )
  }

  if (error instanceof ApiError && error.status === 502) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        <p>Salt-API responded with an error. Check the backend logs for details.</p>
        {detail && <p className="mt-2 font-mono text-xs">{detail}</p>}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Minions</h2>
        <p className="text-sm text-muted-foreground">
          All known minions across every state. Refreshes every 30 seconds.
        </p>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Minion ID</TableHead>
              <TableHead>IP</TableHead>
              <TableHead className="w-32 text-right">Status</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {isPending && (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                  <Loader2 className="mx-auto h-4 w-4 animate-spin" />
                </TableCell>
              </TableRow>
            )}
            {!isPending && data && data.minions.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                  No minions known to the master.
                </TableCell>
              </TableRow>
            )}
            {data?.minions.map((m) => (
              <TableRow key={m.id}>
                <TableCell className="font-mono text-xs">
                  <Link
                    to="/minions/$minionId"
                    params={{ minionId: m.id }}
                    className="flex items-center gap-2 hover:underline"
                  >
                    <Server className="h-3.5 w-3.5 text-muted-foreground" />
                    {m.id}
                  </Link>
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {m.ip || <span className="text-muted-foreground">—</span>}
                </TableCell>
                <TableCell className="text-right">
                  <StatusBadge status={m.status} />
                </TableCell>
                <TableCell className="w-12">
                  {canRun && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" aria-label={`Actions for ${m.id}`}>
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={() => void navigate({ to: '/run', search: { target: m.id, target_type: 'glob' } })}
                        >
                          <Terminal className="mr-2 h-4 w-4" />
                          Run command
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {data && data.minions.length > 0 && (
        <p className="text-sm text-muted-foreground">
          {data.total} minion{data.total === 1 ? '' : 's'} known to the master.
        </p>
      )}
    </div>
  )
}

export function StatusBadge({ status }: { status: MinionStatus }) {
  switch (status) {
    case 'online':
      return (
        <Badge className="bg-emerald-100 text-emerald-900 hover:bg-emerald-100 dark:bg-emerald-950/40 dark:text-emerald-200">
          online
        </Badge>
      )
    case 'offline':
      return <Badge variant="secondary">offline</Badge>
    case 'pending':
      return (
        <Badge className="bg-amber-100 text-amber-900 hover:bg-amber-100 dark:bg-amber-950/40 dark:text-amber-200">
          pending
        </Badge>
      )
    case 'rejected':
      return <Badge variant="destructive">rejected</Badge>
    case 'denied':
      return <Badge variant="destructive">denied</Badge>
  }
}

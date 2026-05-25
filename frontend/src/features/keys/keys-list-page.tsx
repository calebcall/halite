// frontend/src/features/keys/keys-list-page.tsx
import { Key, Loader2, MoreHorizontal } from 'lucide-react'
import { useState } from 'react'

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
import { KeyActionDialog, type KeyAction } from './key-action-dialog'
import type { KeyEntry, KeyStatus } from './api'
import { useKeysList } from './use-keys'

export function KeysListPage() {
  return (
    <MustChangePassword>
      <KeysListPageInner />
    </MustChangePassword>
  )
}

function KeysListPageInner() {
  const { data, isPending, error } = useKeysList()
  const [rowKey, setRowKey] = useState<KeyEntry | null>(null)
  const [rowAction, setRowAction] = useState<KeyAction | null>(null)
  const detail = errorDetail(error)

  if (error instanceof ApiError && error.isForbidden) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        You don&apos;t have permission to view keys.
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
        <p>Salt-API responded with an error.</p>
        {detail && <p className="mt-2 font-mono text-xs">{detail}</p>}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Keys</h2>
        <p className="text-sm text-muted-foreground">
          Minion keys awaiting your approval or already accepted. Refreshes every 30 seconds.
        </p>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Key ID</TableHead>
              <TableHead className="w-32">Status</TableHead>
              <TableHead className="w-12" />
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
            {!isPending && data && data.keys.length === 0 && (
              <TableRow>
                <TableCell colSpan={3} className="h-24 text-center text-muted-foreground">
                  No keys known to the master.
                </TableCell>
              </TableRow>
            )}
            {data?.keys.map((k) => (
              <TableRow key={k.id}>
                <TableCell className="font-mono text-xs">
                  <span className="flex items-center gap-2">
                    <Key className="h-3.5 w-3.5 text-muted-foreground" />
                    {k.id}
                  </span>
                </TableCell>
                <TableCell>
                  <KeyStatusBadge status={k.status} />
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" aria-label={`Actions for ${k.id}`}>
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {actionsFor(k.status).map((a) => (
                        <DropdownMenuItem
                          key={a}
                          onClick={() => { setRowKey(k); setRowAction(a) }}
                          className={a === 'delete' || a === 'reject' ? 'text-destructive focus:text-destructive' : undefined}
                        >
                          {labelFor(a)}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {data && data.keys.length > 0 && (
        <p className="text-sm text-muted-foreground">
          {data.total} key{data.total === 1 ? '' : 's'} on the master.
        </p>
      )}

      {rowKey && rowAction && (
        <KeyActionDialog
          keyId={rowKey.id}
          action={rowAction}
          open
          onOpenChange={(o: boolean) => { if (!o) { setRowAction(null); setRowKey(null) } }}
        />
      )}
    </div>
  )
}

function actionsFor(status: KeyStatus): KeyAction[] {
  switch (status) {
    case 'pending':
      return ['accept', 'reject', 'delete']
    case 'accepted':
      return ['reject', 'delete']
    case 'rejected':
      return ['accept', 'delete']
    case 'denied':
      return ['accept', 'reject', 'delete']
  }
}

function labelFor(action: KeyAction): string {
  switch (action) {
    case 'accept':
      return 'Accept'
    case 'reject':
      return 'Reject'
    case 'delete':
      return 'Delete'
  }
}

function KeyStatusBadge({ status }: { status: KeyStatus }) {
  switch (status) {
    case 'accepted':
      return (
        <Badge className="bg-emerald-100 text-emerald-900 hover:bg-emerald-100 dark:bg-emerald-950/40 dark:text-emerald-200">
          accepted
        </Badge>
      )
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

// frontend/src/features/users/users-list-page.tsx
import { Loader2, MoreHorizontal, Plus } from 'lucide-react'
import { useState } from 'react'

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
import { ApiError } from '@/shared/api/client'
import { MustChangePassword } from '@/features/auth/guards'
import { CreateUserDialog } from './create-user-dialog'
import { DeleteUserDialog } from './delete-user-dialog'
import { EditUserDialog } from './edit-user-dialog'
import { ResetPasswordDialog } from './reset-password-dialog'
import { UserRolesDialog } from './user-roles-dialog'
import type { UserSummary } from './api'
import { useUsersList } from './use-users'

const PAGE_SIZE = 25

type RowDialog = 'edit' | 'reset' | 'roles' | 'delete' | null

export function UsersListPage() {
  return (
    <MustChangePassword>
      <UsersListPageInner />
    </MustChangePassword>
  )
}

function UsersListPageInner() {
  const [page, setPage] = useState(0)
  const [createOpen, setCreateOpen] = useState(false)
  const [rowUser, setRowUser] = useState<UserSummary | null>(null)
  const [rowDialog, setRowDialog] = useState<RowDialog>(null)

  const { data, isPending, error } = useUsersList(PAGE_SIZE, page * PAGE_SIZE)

  if (error instanceof ApiError && error.isForbidden) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        You don&apos;t have permission to view users.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Users</h2>
          <p className="text-sm text-muted-foreground">
            Manage user accounts, passwords, and role assignments.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New user
        </Button>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Username</TableHead>
              <TableHead>Display name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-12" />
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
            {!isPending && data && data.users.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                  No users found.
                </TableCell>
              </TableRow>
            )}
            {data?.users.map((u) => (
              <TableRow key={u.id}>
                <TableCell className="font-medium">
                  {u.username}
                  {u.is_builtin && (
                    <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                      built-in
                    </span>
                  )}
                </TableCell>
                <TableCell>{u.display_name || '—'}</TableCell>
                <TableCell>{u.email || '—'}</TableCell>
                <TableCell>
                  <span
                    className={
                      u.is_active
                        ? 'text-sm text-emerald-600'
                        : 'text-sm text-muted-foreground'
                    }
                  >
                    {u.is_active ? 'Active' : 'Inactive'}
                  </span>
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" aria-label={`Actions for ${u.username}`}>
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => { setRowUser(u); setRowDialog('edit') }}>
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => { setRowUser(u); setRowDialog('roles') }}>
                        Manage roles
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => { setRowUser(u); setRowDialog('reset') }}>
                        Reset password
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => { setRowUser(u); setRowDialog('delete') }}
                        className="text-destructive focus:text-destructive"
                      >
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {data && data.total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Showing {page * PAGE_SIZE + 1}-{Math.min((page + 1) * PAGE_SIZE, data.total)} of {data.total}
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

      <CreateUserDialog open={createOpen} onOpenChange={setCreateOpen} />

      {rowUser && rowDialog === 'edit' && (
        <EditUserDialog
          user={rowUser}
          open
          onOpenChange={(o: boolean) => { if (!o) { setRowDialog(null); setRowUser(null) } }}
        />
      )}
      {rowUser && rowDialog === 'reset' && (
        <ResetPasswordDialog
          user={rowUser}
          open
          onOpenChange={(o: boolean) => { if (!o) { setRowDialog(null); setRowUser(null) } }}
        />
      )}
      {rowUser && rowDialog === 'roles' && (
        <UserRolesDialog
          user={rowUser}
          open
          onOpenChange={(o: boolean) => { if (!o) { setRowDialog(null); setRowUser(null) } }}
        />
      )}
      {rowUser && rowDialog === 'delete' && (
        <DeleteUserDialog
          user={rowUser}
          open
          onOpenChange={(o: boolean) => { if (!o) { setRowDialog(null); setRowUser(null) } }}
        />
      )}
    </div>
  )
}

// frontend/src/features/roles/roles-list-page.tsx
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
import { CreateRoleDialog } from './create-role-dialog'
import { DeleteRoleDialog } from './delete-role-dialog'
import { EditRoleDialog } from './edit-role-dialog'
import { RolePermissionsDialog } from './role-permissions-dialog'
import type { RoleSummary } from './api'
import { useRolesList } from './use-roles'

const PAGE_SIZE = 50

type RowDialog = 'edit' | 'permissions' | 'delete' | null

export function RolesListPage() {
  return (
    <MustChangePassword>
      <RolesListPageInner />
    </MustChangePassword>
  )
}

function RolesListPageInner() {
  const [page, setPage] = useState(0)
  const [createOpen, setCreateOpen] = useState(false)
  const [rowRole, setRowRole] = useState<RoleSummary | null>(null)
  const [rowDialog, setRowDialog] = useState<RowDialog>(null)

  const { data, isPending, error } = useRolesList(PAGE_SIZE, page * PAGE_SIZE)

  if (error instanceof ApiError && error.isForbidden) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        You don&apos;t have permission to view roles.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Roles</h2>
          <p className="text-sm text-muted-foreground">
            Roles bundle permissions. Assign them to users from the Users page.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New role
        </Button>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Description</TableHead>
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
            {!isPending && data && data.roles.length === 0 && (
              <TableRow>
                <TableCell colSpan={3} className="h-24 text-center text-muted-foreground">
                  No roles found.
                </TableCell>
              </TableRow>
            )}
            {data?.roles.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-medium">
                  {r.name}
                  {r.is_builtin && (
                    <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                      built-in
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-muted-foreground">{r.description || '—'}</TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" aria-label={`Actions for ${r.name}`}>
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => { setRowRole(r as RoleSummary); setRowDialog('permissions') }}
                      >
                        Manage permissions
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => { setRowRole(r as RoleSummary); setRowDialog('edit') }}
                      >
                        Edit description
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => { setRowRole(r as RoleSummary); setRowDialog('delete') }}
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

      <CreateRoleDialog open={createOpen} onOpenChange={setCreateOpen} />

      {rowRole && rowDialog === 'permissions' && (
        <RolePermissionsDialog
          role={rowRole}
          open
          onOpenChange={(o: boolean) => { if (!o) { setRowDialog(null); setRowRole(null) } }}
        />
      )}
      {rowRole && rowDialog === 'edit' && (
        <EditRoleDialog
          role={rowRole}
          open
          onOpenChange={(o: boolean) => { if (!o) { setRowDialog(null); setRowRole(null) } }}
        />
      )}
      {rowRole && rowDialog === 'delete' && (
        <DeleteRoleDialog
          role={rowRole}
          open
          onOpenChange={(o: boolean) => { if (!o) { setRowDialog(null); setRowRole(null) } }}
        />
      )}
    </div>
  )
}

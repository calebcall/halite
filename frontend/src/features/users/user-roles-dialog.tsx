// frontend/src/features/users/user-roles-dialog.tsx
import { Loader2 } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { UserSummary } from './api'
import {
  useAddUserRole,
  useRemoveUserRole,
  useRolesList,
  useUserRoles,
} from './use-users'

export function UserRolesDialog({
  user,
  open,
  onOpenChange,
}: {
  user: UserSummary
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { data: roles, isPending: rolesPending } = useRolesList()
  const { data: userRoleIds, isPending: userRolesPending } = useUserRoles(user.id)
  const addRole = useAddUserRole(user.id)
  const removeRole = useRemoveUserRole(user.id)
  const [error, setError] = useState<string | null>(null)
  const [pendingRoleId, setPendingRoleId] = useState<string | null>(null)

  async function toggle(roleId: string, checked: boolean) {
    setError(null)
    setPendingRoleId(roleId)
    try {
      if (checked) {
        await addRole.mutateAsync(roleId)
      } else {
        await removeRole.mutateAsync(roleId)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Role change failed.')
    } finally {
      setPendingRoleId(null)
    }
  }

  const ready = !rolesPending && !userRolesPending && roles && userRoleIds

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Roles — {user.username}</DialogTitle>
          <DialogDescription>
            Changes apply immediately. Toggle a role to add or remove it.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2 rounded-md border p-3">
          {!ready && (
            <div className="flex items-center justify-center py-4 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
            </div>
          )}
          {ready &&
            roles!.roles.map((r) => {
              const checked = userRoleIds!.includes(r.id)
              const busy = pendingRoleId === r.id
              return (
                <label key={r.id} className="flex items-center justify-between gap-3 py-1.5 text-sm">
                  <div className="flex items-center gap-2">
                    <Checkbox
                      checked={checked}
                      disabled={busy}
                      onCheckedChange={(c) => void toggle(r.id, c === true)}
                    />
                    <div>
                      <div className="font-medium">{r.name}</div>
                      {r.description && (
                        <div className="text-xs text-muted-foreground">{r.description}</div>
                      )}
                    </div>
                  </div>
                  {busy && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
                </label>
              )
            })}
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

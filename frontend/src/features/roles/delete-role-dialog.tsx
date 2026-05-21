// frontend/src/features/roles/delete-role-dialog.tsx
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ApiError } from '@/shared/api/client'
import type { RoleSummary } from './api'
import { useDeleteRole } from './use-roles'

export function DeleteRoleDialog({
  role,
  open,
  onOpenChange,
}: {
  role: RoleSummary
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const deleteRole = useDeleteRole()
  const [serverError, setServerError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const disabled = role.is_builtin

  async function onConfirm() {
    if (disabled) return
    setServerError(null)
    setPending(true)
    try {
      await deleteRole.mutateAsync(role.id)
      onOpenChange(false)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setServerError(
          (e.body && typeof e.body === 'object' && 'detail' in e.body
            ? String((e.body as Record<string, unknown>).detail)
            : null) ?? 'Cannot delete this role.',
        )
      } else {
        setServerError(e instanceof Error ? e.message : 'Delete failed.')
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete role?</DialogTitle>
          <DialogDescription>
            This permanently removes <strong>{role.name}</strong> and revokes the role from every
            user who currently has it. This cannot be undone.
            {disabled && (
              <span className="mt-2 block text-sm text-destructive">
                Built-in roles cannot be deleted.
              </span>
            )}
          </DialogDescription>
        </DialogHeader>
        {serverError && <p className="text-sm text-destructive">{serverError}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() => void onConfirm()}
            disabled={pending || disabled}
          >
            {pending ? 'Deleting…' : 'Delete role'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

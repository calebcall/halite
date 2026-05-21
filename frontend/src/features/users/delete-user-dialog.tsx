// frontend/src/features/users/delete-user-dialog.tsx
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
import type { UserSummary } from './api'
import { useDeleteUser } from './use-users'

export function DeleteUserDialog({
  user,
  open,
  onOpenChange,
}: {
  user: UserSummary
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const deleteUser = useDeleteUser()
  const [serverError, setServerError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const disabled = user.is_builtin

  async function onConfirm() {
    if (disabled) return
    setServerError(null)
    setPending(true)
    try {
      await deleteUser.mutateAsync(user.id)
      onOpenChange(false)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setServerError(
          (e.body && typeof e.body === 'object' && 'detail' in e.body
            ? String((e.body as Record<string, unknown>).detail)
            : null) ?? 'Cannot delete this user.',
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
          <DialogTitle>Delete user?</DialogTitle>
          <DialogDescription>
            This permanently removes <strong>{user.username}</strong>. Any sessions they hold are
            also revoked. This cannot be undone.
            {disabled && (
              <span className="mt-2 block text-sm text-destructive">
                Built-in users cannot be deleted.
              </span>
            )}
          </DialogDescription>
        </DialogHeader>
        {serverError && <p className="text-sm text-destructive">{serverError}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={() => void onConfirm()} disabled={pending || disabled}>
            {pending ? 'Deleting…' : 'Delete user'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// frontend/src/features/keys/key-action-dialog.tsx
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
import { useAcceptKey, useDeleteKey, useRejectKey } from './use-keys'

export type KeyAction = 'accept' | 'reject' | 'delete'

const COPY: Record<KeyAction, { title: string; body: string; cta: string; cta_progress: string; variant: 'default' | 'destructive' }> = {
  accept: {
    title: 'Accept key',
    body: 'This grants the minion permission to communicate with the master.',
    cta: 'Accept key',
    cta_progress: 'Accepting…',
    variant: 'default',
  },
  reject: {
    title: 'Reject key',
    body: 'This blocks the minion from communicating with the master. The minion key remains on disk.',
    cta: 'Reject key',
    cta_progress: 'Rejecting…',
    variant: 'destructive',
  },
  delete: {
    title: 'Delete key',
    body: 'This removes the minion key entirely. The minion will have to re-register from scratch. This cannot be undone.',
    cta: 'Delete key',
    cta_progress: 'Deleting…',
    variant: 'destructive',
  },
}

export function KeyActionDialog({
  keyId,
  action,
  open,
  onOpenChange,
}: {
  keyId: string
  action: KeyAction
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const acceptMutation = useAcceptKey()
  const rejectMutation = useRejectKey()
  const deleteMutation = useDeleteKey()
  const [serverError, setServerError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const copy = COPY[action]

  async function onConfirm() {
    setServerError(null)
    setPending(true)
    try {
      if (action === 'accept') {
        await acceptMutation.mutateAsync(keyId)
      } else if (action === 'reject') {
        await rejectMutation.mutateAsync(keyId)
      } else {
        await deleteMutation.mutateAsync(keyId)
      }
      onOpenChange(false)
    } catch (e) {
      if (e instanceof ApiError && e.status === 502) {
        setServerError('Salt-API returned an error. Check the backend logs.')
      } else if (e instanceof ApiError && e.status === 503) {
        setServerError('Salt-API is not reachable.')
      } else if (e instanceof ApiError && e.isForbidden) {
        setServerError(`You don't have permission to ${action} this key.`)
      } else {
        setServerError(e instanceof Error ? e.message : `${copy.cta} failed.`)
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{copy.title}</DialogTitle>
          <DialogDescription>
            <span className="font-mono text-foreground">{keyId}</span>
            <span className="mt-2 block text-muted-foreground">{copy.body}</span>
          </DialogDescription>
        </DialogHeader>
        {serverError && <p className="text-sm text-destructive">{serverError}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant={copy.variant}
            disabled={pending}
            onClick={() => void onConfirm()}
          >
            {pending ? copy.cta_progress : copy.cta}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// frontend/src/features/jobs/kill-job-dialog.tsx
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
import { ApiError, errorDetail } from '@/shared/api/client'
import { useKillJob } from './use-jobs'

export function KillJobDialog({
  jid,
  jobFunction,
  jobTarget,
  open,
  onOpenChange,
}: {
  jid: string
  jobFunction: string
  jobTarget: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const mutation = useKillJob()
  const [serverError, setServerError] = useState<string | null>(null)
  const pending = mutation.isPending

  async function onConfirm() {
    setServerError(null)
    try {
      await mutation.mutateAsync(jid)
      onOpenChange(false)
    } catch (e) {
      if (e instanceof ApiError && e.isForbidden) {
        setServerError("You don't have permission to kill this job.")
      } else if (e instanceof ApiError && e.status === 502) {
        const detail = errorDetail(e)
        setServerError(detail ? `Salt-API returned an error: ${detail}` : 'Salt-API returned an error.')
      } else if (e instanceof ApiError && e.status === 503) {
        setServerError('Salt-API is not reachable.')
      } else {
        setServerError(e instanceof Error ? e.message : 'Kill failed.')
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Kill job</DialogTitle>
          <DialogDescription>
            <span className="font-mono text-foreground">{jid}</span>
            <span className="mt-2 block text-muted-foreground">
              Signals every minion executing <span className="font-mono">{jobFunction}</span> on <span className="font-mono">{jobTarget || 'no target'}</span> to abort. This cannot be undone, but minions that haven&apos;t yet started the job may still execute it.
            </span>
          </DialogDescription>
        </DialogHeader>
        {serverError && <p className="text-sm text-destructive">{serverError}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={pending}
            onClick={() => void onConfirm()}
          >
            {pending ? 'Killing…' : 'Kill job'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

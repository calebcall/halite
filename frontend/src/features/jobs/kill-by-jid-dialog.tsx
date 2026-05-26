// frontend/src/features/jobs/kill-by-jid-dialog.tsx
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError, errorDetail } from '@/shared/api/client'
import { useKillJob } from './use-jobs'

// Salt jids are decimal timestamps — typically 20 digits like
// YYYYMMDDHHMMSSffffff. Accept 15+ digits to be slightly tolerant of
// edge cases (older salt versions, microsecond truncation).
const JID_RE = /^\d{15,}$/

export function KillByJidDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const mutation = useKillJob()
  const [jid, setJid] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)
  const pending = mutation.isPending

  async function onConfirm() {
    setServerError(null)
    setValidationError(null)
    const trimmed = jid.trim()
    if (!JID_RE.test(trimmed)) {
      setValidationError('JIDs are numeric strings of 15+ digits (e.g. 20260123120000000000).')
      return
    }
    try {
      await mutation.mutateAsync(trimmed)
      setJid('')
      onOpenChange(false)
    } catch (e) {
      if (e instanceof ApiError && e.isForbidden) {
        setServerError("You don't have permission to kill jobs.")
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
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setJid('')
          setValidationError(null)
          setServerError(null)
        }
        onOpenChange(o)
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Kill job by JID</DialogTitle>
          <DialogDescription>
            Signal the salt master to abort the given job. Works even when the
            job has been evicted from the master&apos;s job cache —
            <span className="font-mono text-foreground"> runner.saltutil.kill_job</span> broadcasts
            directly to minions.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <Label htmlFor="killjid">JID</Label>
          <Input
            id="killjid"
            value={jid}
            onChange={(e) => setJid(e.target.value)}
            placeholder="20260123120000000000"
            className="font-mono"
            autoFocus
          />
        </div>
        {validationError && <p className="text-sm text-destructive">{validationError}</p>}
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

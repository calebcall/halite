// frontend/src/features/roles/role-permissions-dialog.tsx
import { AlertTriangle, Loader2, Trash2 } from 'lucide-react'
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
import type { PermissionOut, RoleSummary } from './api'
import { useAddPermission, useRemovePermission, useRole } from './use-roles'

export function RolePermissionsDialog({
  role,
  open,
  onOpenChange,
}: {
  role: RoleSummary
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { data: detail, isPending } = useRole(role.id)
  const addPermission = useAddPermission(role.id)
  const removePermission = useRemovePermission(role.id)

  const [verb, setVerb] = useState('')
  const [resourceGlob, setResourceGlob] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pendingPermissionId, setPendingPermissionId] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  async function onAdd() {
    setError(null)
    if (!verb.trim() || !resourceGlob.trim()) {
      setError('Both verb and resource pattern are required.')
      return
    }
    setAdding(true)
    try {
      await addPermission.mutateAsync({
        verb: verb.trim(),
        resource_glob: resourceGlob.trim(),
      })
      setVerb('')
      setResourceGlob('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Add failed.')
    } finally {
      setAdding(false)
    }
  }

  async function onRemove(permission: PermissionOut) {
    setError(null)
    setPendingPermissionId(permission.id)
    try {
      await removePermission.mutateAsync(permission.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Remove failed.')
    } finally {
      setPendingPermissionId(null)
    }
  }

  const permissions = detail?.permissions ?? []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Permissions — {role.name}</DialogTitle>
          <DialogDescription>
            Each permission is a <code>(verb, resource pattern)</code> pair. Resource patterns
            use shell-style wildcards (e.g. <code>state.*</code>, <code>key:web-*</code>,{' '}
            <code>*</code>).
          </DialogDescription>
        </DialogHeader>

        {role.is_builtin && (
          <div className="flex items-start gap-2 rounded-md border border-amber-400/40 bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              Modifying permissions on built-in roles can lock users out. Proceed with caution.
            </span>
          </div>
        )}

        <div className="space-y-2 rounded-md border p-3">
          {isPending && (
            <div className="flex items-center justify-center py-4 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
            </div>
          )}
          {!isPending && permissions.length === 0 && (
            <div className="py-4 text-center text-sm text-muted-foreground">
              No permissions yet. Add one below.
            </div>
          )}
          {!isPending &&
            permissions.map((p) => {
              const busy = pendingPermissionId === p.id
              return (
                <div
                  key={p.id}
                  className="flex items-center justify-between rounded-md border bg-background px-3 py-2 text-sm"
                >
                  <div className="flex items-center gap-2 font-mono text-xs">
                    <span className="rounded bg-muted px-1.5 py-0.5 font-medium">{p.verb}</span>
                    <span className="text-muted-foreground">·</span>
                    <span>{p.resource_glob}</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={busy}
                    onClick={() => void onRemove(p)}
                    aria-label={`Remove ${p.verb} ${p.resource_glob}`}
                  >
                    {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                  </Button>
                </div>
              )
            })}
        </div>

        <div className="space-y-2 rounded-md border p-3">
          <div className="grid grid-cols-[1fr_2fr] gap-2">
            <div className="space-y-1">
              <Label htmlFor="new-verb" className="text-xs">Verb</Label>
              <Input
                id="new-verb"
                placeholder="run"
                value={verb}
                onChange={(e) => setVerb(e.target.value)}
                autoComplete="off"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="new-resource" className="text-xs">Resource pattern</Label>
              <Input
                id="new-resource"
                placeholder="state.*"
                value={resourceGlob}
                onChange={(e) => setResourceGlob(e.target.value)}
                autoComplete="off"
              />
            </div>
          </div>
          <div className="flex justify-end">
            <Button size="sm" disabled={adding || !verb.trim() || !resourceGlob.trim()} onClick={() => void onAdd()}>
              {adding ? 'Adding…' : 'Add permission'}
            </Button>
          </div>
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

// frontend/src/features/run/template-picker.tsx
import { Trash2, Users } from 'lucide-react'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useCurrentUser } from '@/features/auth/use-current-user'
import { type CommandTemplate, useDeleteTemplate, useTemplates, useUpdateTemplate } from './use-templates'

export function TemplatePicker({
  onSelect,
}: {
  onSelect: (template: CommandTemplate) => void
}) {
  const { data } = useTemplates()
  const { data: currentUser } = useCurrentUser()
  const [manageOpen, setManageOpen] = useState(false)
  const templates = data?.templates ?? []

  function handleChange(id: string) {
    const t = templates.find((x) => x.id === id)
    if (t) onSelect(t)
  }

  return (
    <>
      <div className="flex items-end gap-2">
        <Select onValueChange={handleChange} value="">
          <SelectTrigger className="max-w-md">
            <SelectValue
              placeholder={templates.length === 0 ? 'No templates yet' : 'Load template…'}
            />
          </SelectTrigger>
          <SelectContent>
            {templates.map((t) => {
              const isOwner = currentUser != null && t.owner_username === currentUser.username
              return (
                <SelectItem key={t.id} value={t.id}>
                  <div className="flex items-center justify-between gap-3 w-full">
                    <div className="min-w-0">
                      <div className="font-medium truncate">{t.name}</div>
                      {t.description && (
                        <div className="text-xs text-muted-foreground truncate">{t.description}</div>
                      )}
                      {!isOwner && (
                        <div className="flex items-center text-xs text-muted-foreground truncate">
                          <Users className="size-3 mr-1 shrink-0" />
                          Shared by {t.owner_username}
                        </div>
                      )}
                    </div>
                  </div>
                </SelectItem>
              )
            })}
          </SelectContent>
        </Select>
        {templates.length > 0 && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setManageOpen(true)}
            aria-label="Manage templates"
            className="text-muted-foreground"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        )}
      </div>

      {manageOpen && (
        <ManageTemplatesDialog
          templates={templates}
          onClose={() => setManageOpen(false)}
          onDeleteSuccess={() => {
            if (templates.length === 1) setManageOpen(false)
          }}
        />
      )}
    </>
  )
}

function ManageTemplatesDialog({
  templates,
  onClose,
  onDeleteSuccess,
}: {
  templates: CommandTemplate[]
  onClose: () => void
  onDeleteSuccess: () => void
}) {
  const { data: currentUser } = useCurrentUser()
  const deleteMut = useDeleteTemplate()
  const updateMut = useUpdateTemplate()
  const [updateError, setUpdateError] = useState<string | null>(null)

  function handleDelete(id: string) {
    deleteMut.mutate(id, { onSuccess: onDeleteSuccess })
  }

  function handleShareToggle(template: CommandTemplate, newValue: boolean) {
    setUpdateError(null)
    updateMut.mutate(
      { body: { is_shared: newValue }, id: template.id },
      {
        onError: (err) => {
          setUpdateError(err instanceof Error ? err.message : 'Failed to update sharing.')
        },
      },
    )
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Manage templates</DialogTitle>
          <DialogDescription>Delete or share templates you own.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2 max-h-80 overflow-auto">
          {templates.map((t) => {
            const isOwner = currentUser != null && t.owner_username === currentUser.username
            const isUpdatingThisRow = updateMut.isPending && updateMut.variables?.id === t.id

            return (
              <div
                key={t.id}
                className="flex items-start justify-between gap-3 rounded-md border p-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-medium truncate">{t.name}</div>
                  {t.description && (
                    <div className="text-xs text-muted-foreground">{t.description}</div>
                  )}
                  <div className="mt-1 text-xs text-muted-foreground font-mono truncate">
                    {t.target} · {t.fun}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {isOwner ? (
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-muted-foreground">Shared</span>
                      <Switch
                        checked={t.is_shared}
                        disabled={isUpdatingThisRow}
                        onCheckedChange={(checked) => handleShareToggle(t, checked)}
                        aria-label={`Share ${t.name}`}
                      />
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      Shared by {t.owner_username}
                    </span>
                  )}

                  {isOwner && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={deleteMut.isPending}
                      className="text-destructive hover:text-destructive"
                      onClick={() => handleDelete(t.id)}
                      aria-label={`Delete ${t.name}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
        {updateError && <p className="text-sm text-destructive">{updateError}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

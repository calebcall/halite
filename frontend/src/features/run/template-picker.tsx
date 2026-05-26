// frontend/src/features/run/template-picker.tsx
import { Trash2 } from 'lucide-react'
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
import { type CommandTemplate, useDeleteTemplate, useTemplates } from './use-templates'

export function TemplatePicker({
  onSelect,
}: {
  onSelect: (template: CommandTemplate) => void
}) {
  const { data } = useTemplates()
  const deleteMutation = useDeleteTemplate()
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
            {templates.map((t) => (
              <SelectItem key={t.id} value={t.id}>
                <div className="flex items-center justify-between gap-3 w-full">
                  <div className="min-w-0">
                    <div className="font-medium truncate">{t.name}</div>
                    {t.description && (
                      <div className="text-xs text-muted-foreground truncate">{t.description}</div>
                    )}
                  </div>
                </div>
              </SelectItem>
            ))}
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
          deleting={deleteMutation.isPending}
          onClose={() => setManageOpen(false)}
          onDelete={(id) => {
            deleteMutation.mutate(id, {
              onSuccess: () => {
                // Close when there are no more templates
                if (templates.length === 1) setManageOpen(false)
              },
            })
          }}
        />
      )}
    </>
  )
}

function ManageTemplatesDialog({
  templates,
  deleting,
  onClose,
  onDelete,
}: {
  templates: CommandTemplate[]
  deleting: boolean
  onClose: () => void
  onDelete: (id: string) => void
}) {
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Manage templates</DialogTitle>
          <DialogDescription>Delete templates you no longer need.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2 max-h-80 overflow-auto">
          {templates.map((t) => (
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
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={deleting}
                className="text-destructive hover:text-destructive shrink-0"
                onClick={() => onDelete(t.id)}
                aria-label={`Delete ${t.name}`}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

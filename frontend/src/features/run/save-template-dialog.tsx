// frontend/src/features/run/save-template-dialog.tsx
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
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, errorDetail } from '@/shared/api/client'
import { type CommandTemplateCreate, useCreateTemplate } from './use-templates'

export function SaveTemplateDialog({
  open,
  onOpenChange,
  body,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  // Current RunCommandPage form values (minus name/description/is_shared)
  body: Omit<CommandTemplateCreate, 'description' | 'is_shared' | 'name'>
}) {
  const mutation = useCreateTemplate()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [isShared, setIsShared] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const pending = mutation.isPending

  async function onConfirm() {
    setServerError(null)
    const trimmed = name.trim()
    if (!trimmed) {
      setServerError('Template name is required.')
      return
    }
    if (trimmed.length > 100) {
      setServerError('Template name is too long (max 100 characters).')
      return
    }
    try {
      await mutation.mutateAsync({
        ...body,
        description: description.trim(),
        is_shared: isShared,
        name: trimmed,
      })
      setName('')
      setDescription('')
      setIsShared(false)
      onOpenChange(false)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setServerError('You already have a template with that name.')
      } else if (e instanceof ApiError && e.status === 422) {
        const detail = errorDetail(e)
        setServerError(detail ?? 'Invalid input.')
      } else {
        setServerError(e instanceof Error ? e.message : 'Save failed.')
      }
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setName('')
          setDescription('')
          setIsShared(false)
          setServerError(null)
        }
        onOpenChange(o)
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Save as template</DialogTitle>
          <DialogDescription>
            Saves the current form values so you can reload them later.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <Label htmlFor="tpl-name">Name</Label>
          <Input
            id="tpl-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Web prod dry-run highstate"
            autoFocus
            maxLength={100}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="tpl-desc">Description (optional)</Label>
          <Textarea
            id="tpl-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            maxLength={500}
            placeholder="What does this template do?"
          />
        </div>
        <div className="flex items-center justify-between gap-4">
          <div className="grid gap-1">
            <Label htmlFor="tpl-shared">Share with team</Label>
            <p className="text-sm text-muted-foreground">
              Anyone signed in can see and run this template.
            </p>
          </div>
          <Switch
            id="tpl-shared"
            checked={isShared}
            onCheckedChange={setIsShared}
          />
        </div>
        {serverError && <p className="text-sm text-destructive">{serverError}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button disabled={pending} onClick={() => void onConfirm()}>
            {pending ? 'Saving…' : 'Save template'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// frontend/src/features/roles/edit-role-dialog.tsx
import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

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
import type { RoleSummary } from './api'
import { useUpdateRole } from './use-roles'

const schema = z.object({
  description: z.string().max(255),
})

type FormValues = z.infer<typeof schema>

export function EditRoleDialog({
  role,
  open,
  onOpenChange,
}: {
  role: RoleSummary
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const updateRole = useUpdateRole(role.id)
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { description: role.description || '' },
  })

  async function onSubmit(values: FormValues) {
    setServerError(null)
    try {
      await updateRole.mutateAsync({ description: values.description })
      onOpenChange(false)
    } catch (e) {
      setServerError(e instanceof Error ? e.message : 'Update failed.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit role — {role.name}</DialogTitle>
          <DialogDescription>
            Role names are immutable. Use this to update the description only.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Input id="description" autoFocus {...register('description')} />
            {errors.description && (
              <p className="text-sm text-destructive">{errors.description.message}</p>
            )}
          </div>
          {serverError && <p className="text-sm text-destructive">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Saving…' : 'Save changes'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

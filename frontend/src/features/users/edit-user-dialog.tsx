// frontend/src/features/users/edit-user-dialog.tsx
import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import type { UserSummary } from './api'
import { useUpdateUser } from './use-users'

const schema = z.object({
  display_name: z.string().max(255),
  email: z.string().email('Invalid email').or(z.literal('')),
  is_active: z.boolean(),
})

type FormValues = z.infer<typeof schema>

export function EditUserDialog({
  user,
  open,
  onOpenChange,
}: {
  user: UserSummary
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const updateUser = useUpdateUser(user.id)
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      display_name: user.display_name || '',
      email: user.email || '',
      is_active: user.is_active,
    },
  })

  async function onSubmit(values: FormValues) {
    setServerError(null)
    try {
      await updateUser.mutateAsync({
        display_name: values.display_name,
        email: values.email || null,
        is_active: values.is_active,
      })
      onOpenChange(false)
    } catch (e) {
      setServerError(e instanceof Error ? e.message : 'Update failed.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit user — {user.username}</DialogTitle>
        </DialogHeader>
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className="space-y-2">
            <Label htmlFor="display_name">Display name</Label>
            <Input id="display_name" {...register('display_name')} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" {...register('email')} />
            {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
          </div>
          <div className="flex items-center justify-between rounded-md border p-3">
            <Label htmlFor="is_active" className="text-sm font-medium">
              Active
            </Label>
            <Switch
              id="is_active"
              checked={watch('is_active')}
              onCheckedChange={(c) => setValue('is_active', c)}
            />
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

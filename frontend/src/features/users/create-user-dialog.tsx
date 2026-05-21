// frontend/src/features/users/create-user-dialog.tsx
import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
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
import { ApiError } from '@/shared/api/client'
import { useCreateUser, useRolesList } from './use-users'

const schema = z.object({
  username: z.string().min(1, 'Username is required').max(255),
  display_name: z.string().max(255).optional(),
  email: z.string().email('Invalid email').or(z.literal('')).optional(),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  must_change_pw: z.boolean(),
  role_ids: z.array(z.string()),
})

type FormValues = z.infer<typeof schema>

export function CreateUserDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { data: rolesData } = useRolesList()
  const createUser = useCreateUser()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { must_change_pw: true, role_ids: [] },
  })

  const selectedRoleIds = watch('role_ids')

  async function onSubmit(values: FormValues) {
    setServerError(null)
    try {
      await createUser.mutateAsync({
        username: values.username,
        display_name: values.display_name || '',
        email: values.email || null,
        password: values.password,
        must_change_pw: values.must_change_pw,
        role_ids: values.role_ids,
      })
      reset()
      onOpenChange(false)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setServerError('Username already exists.')
      } else {
        setServerError(e instanceof Error ? e.message : 'Create failed.')
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) reset(); onOpenChange(o) }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create user</DialogTitle>
          <DialogDescription>
            New users land with <em>must change password</em> on by default.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input id="username" autoFocus autoComplete="off" {...register('username')} />
            {errors.username && (
              <p className="text-sm text-destructive">{errors.username.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="display_name">Display name</Label>
            <Input id="display_name" autoComplete="off" {...register('display_name')} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="off" {...register('email')} />
            {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Initial password</Label>
            <Input id="password" type="password" autoComplete="new-password" {...register('password')} />
            {errors.password && (
              <p className="text-sm text-destructive">{errors.password.message}</p>
            )}
          </div>
          <div className="flex items-center justify-between rounded-md border p-3">
            <div className="space-y-0.5">
              <Label htmlFor="must_change_pw" className="text-sm font-medium">
                Force password change on first login
              </Label>
            </div>
            <Switch
              id="must_change_pw"
              checked={watch('must_change_pw')}
              onCheckedChange={(c) => setValue('must_change_pw', c)}
            />
          </div>
          {rolesData && rolesData.roles.length > 0 && (
            <div className="space-y-2">
              <Label>Initial roles</Label>
              <div className="grid grid-cols-2 gap-2 rounded-md border p-3">
                {rolesData.roles.map((r) => {
                  const checked = selectedRoleIds.includes(r.id)
                  return (
                    <label key={r.id} className="flex items-center gap-2 text-sm">
                      <Checkbox
                        checked={checked}
                        onCheckedChange={(c) => {
                          const next = c
                            ? [...selectedRoleIds, r.id]
                            : selectedRoleIds.filter((id) => id !== r.id)
                          setValue('role_ids', next)
                        }}
                      />
                      <span>{r.name}</span>
                    </label>
                  )
                })}
              </div>
            </div>
          )}
          {serverError && <p className="text-sm text-destructive">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Creating…' : 'Create user'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

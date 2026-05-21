// frontend/src/features/users/reset-password-dialog.tsx
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
import { Switch } from '@/components/ui/switch'
import type { UserSummary } from './api'
import { useResetUserPassword } from './use-users'

const schema = z
  .object({
    new_password: z.string().min(8, 'Password must be at least 8 characters'),
    confirm_password: z.string().min(1, 'Confirm the new password'),
    must_change_pw: z.boolean(),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    message: 'Passwords must match',
    path: ['confirm_password'],
  })

type FormValues = z.infer<typeof schema>

export function ResetPasswordDialog({
  user,
  open,
  onOpenChange,
}: {
  user: UserSummary
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const resetPassword = useResetUserPassword(user.id)
  const [serverError, setServerError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { must_change_pw: true },
  })

  async function onSubmit(values: FormValues) {
    setServerError(null)
    setSuccess(false)
    try {
      await resetPassword.mutateAsync({
        new_password: values.new_password,
        must_change_pw: values.must_change_pw,
      })
      setSuccess(true)
      reset({ must_change_pw: true })
    } catch (e) {
      setServerError(e instanceof Error ? e.message : 'Reset failed.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) { reset({ must_change_pw: true }); setSuccess(false); setServerError(null) } onOpenChange(o) }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Reset password — {user.username}</DialogTitle>
          <DialogDescription>
            All of this user&apos;s active sessions will be revoked.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className="space-y-2">
            <Label htmlFor="new_password">New password</Label>
            <Input
              id="new_password"
              type="password"
              autoComplete="new-password"
              autoFocus
              {...register('new_password')}
            />
            {errors.new_password && (
              <p className="text-sm text-destructive">{errors.new_password.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm_password">Confirm password</Label>
            <Input
              id="confirm_password"
              type="password"
              autoComplete="new-password"
              {...register('confirm_password')}
            />
            {errors.confirm_password && (
              <p className="text-sm text-destructive">{errors.confirm_password.message}</p>
            )}
          </div>
          <div className="flex items-center justify-between rounded-md border p-3">
            <Label htmlFor="must_change_pw" className="text-sm font-medium">
              Force password change on next login
            </Label>
            <Switch
              id="must_change_pw"
              checked={watch('must_change_pw')}
              onCheckedChange={(c) => setValue('must_change_pw', c)}
            />
          </div>
          {serverError && <p className="text-sm text-destructive">{serverError}</p>}
          {success && <p className="text-sm text-emerald-600">Password reset.</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Resetting…' : 'Reset password'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// frontend/src/features/auth/change-password-page.tsx
import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from '@tanstack/react-router'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '@/shared/api/client'
import { useChangePassword, useCurrentUser } from './use-current-user'

const schema = z
  .object({
    current_password: z.string().min(1, 'Current password is required'),
    new_password: z.string().min(8, 'New password must be at least 8 characters'),
    confirm_new_password: z.string().min(1, 'Confirm the new password'),
  })
  .refine((v) => v.new_password === v.confirm_new_password, {
    message: 'New password and confirmation must match',
    path: ['confirm_new_password'],
  })
  .refine((v) => v.current_password !== v.new_password, {
    message: 'New password must differ from current password',
    path: ['new_password'],
  })

type FormValues = z.infer<typeof schema>

export function ChangePasswordPage() {
  const { data: user } = useCurrentUser()
  const changePassword = useChangePassword()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const forced = user?.must_change_pw === true

  async function onSubmit(values: FormValues) {
    setServerError(null)
    setSuccess(false)
    try {
      await changePassword(values.current_password, values.new_password)
      setSuccess(true)
      reset()
      if (forced) {
        void navigate({ to: '/', replace: true })
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setServerError('Current password is incorrect.')
      } else {
        setServerError(e instanceof Error ? e.message : 'Change password failed.')
      }
    }
  }

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-2xl font-semibold">
            {forced ? 'Set a new password' : 'Change password'}
          </CardTitle>
          {forced && (
            <p className="text-sm text-muted-foreground">
              You must set a new password before continuing.
            </p>
          )}
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
            <div className="space-y-2">
              <Label htmlFor="current_password">Current password</Label>
              <Input
                id="current_password"
                type="password"
                autoComplete="current-password"
                autoFocus
                {...register('current_password')}
              />
              {errors.current_password && (
                <p className="text-sm text-destructive">{errors.current_password.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="new_password">New password</Label>
              <Input
                id="new_password"
                type="password"
                autoComplete="new-password"
                {...register('new_password')}
              />
              {errors.new_password && (
                <p className="text-sm text-destructive">{errors.new_password.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm_new_password">Confirm new password</Label>
              <Input
                id="confirm_new_password"
                type="password"
                autoComplete="new-password"
                {...register('confirm_new_password')}
              />
              {errors.confirm_new_password && (
                <p className="text-sm text-destructive">{errors.confirm_new_password.message}</p>
              )}
            </div>
            {serverError && <p className="text-sm text-destructive">{serverError}</p>}
            {success && !forced && (
              <p className="text-sm text-emerald-600">Password updated.</p>
            )}
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? 'Saving…' : 'Update password'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

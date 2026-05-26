import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { BrandMark } from '@/app/layout/BrandMark'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '@/shared/api/client'
import { useAuthActions } from './use-current-user'

const schema = z.object({
  username: z.string().min(1, 'Username is required'),
  password: z.string().min(1, 'Password is required'),
})

type FormValues = z.infer<typeof schema>

export function LoginPage() {
  const { login } = useAuthActions()
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  async function onSubmit(values: FormValues) {
    setServerError(null)
    try {
      await login(values.username, values.password)
      // PublicOnly guard will redirect once useCurrentUser resolves.
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setServerError('Invalid username or password.')
      } else {
        setServerError(e instanceof Error ? e.message : 'Login failed.')
      }
    }
  }

  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-background p-4">
      <BackgroundGlow />
      <div className="relative z-10 w-full max-w-sm">
        <div className="mb-6 flex items-center gap-3">
          <BrandMark className="h-11 w-11" />
          <div className="flex flex-col leading-tight">
            <span className="text-base font-semibold tracking-tight">Halite</span>
            <span className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              Salt Console
            </span>
          </div>
        </div>
        <div className="rounded-xl border border-border/80 bg-card/80 p-6 shadow-lg shadow-black/20 backdrop-blur">
          <div className="mb-5">
            <h1 className="text-xl font-semibold tracking-tight">Sign in</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Enter your credentials to continue.
            </p>
          </div>
          <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input id="username" autoFocus autoComplete="username" {...register('username')} />
              {errors.username && (
                <p className="text-sm text-destructive">{errors.username.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                {...register('password')}
              />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>
            {serverError && (
              <div
                role="alert"
                aria-live="polite"
                className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                {serverError}
              </div>
            )}
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}

function BackgroundGlow() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0">
      <div className="absolute -top-32 left-1/2 h-72 w-[36rem] -translate-x-1/2 rounded-full bg-primary/10 blur-3xl" />
      <div className="absolute bottom-0 left-1/2 h-px w-2/3 -translate-x-1/2 bg-gradient-to-r from-transparent via-border to-transparent" />
    </div>
  )
}

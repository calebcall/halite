// frontend/src/features/setup/setup-wizard-page.tsx
import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { Check, Loader2, RefreshCw, X } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import {
  settingsKeys,
  useTestSalt,
  useUpdateSalt,
} from '@/features/admin/use-settings'
import type { components } from '@/shared/api/types.gen'

type TestSaltConnectionOut = components['schemas']['TestSaltConnectionOut']

const setupSchema = z.object({
  eauth: z.enum(['pam', 'sharedsecret', 'ldap', 'file', 'auto']),
  password: z.string().min(1, 'Password is required'),
  url: z.string().min(1, 'URL is required'),
  username: z.string().min(1, 'Username is required'),
  verify: z.boolean(),
})

type SetupFormValues = z.infer<typeof setupSchema>

export function SetupWizardPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const testMut = useTestSalt()
  const saveMut = useUpdateSalt()
  const [testResult, setTestResult] = useState<TestSaltConnectionOut | null>(null)
  const [testOk, setTestOk] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<SetupFormValues>({
    defaultValues: {
      eauth: 'pam',
      password: '',
      url: '',
      username: '',
      verify: true,
    },
    resolver: zodResolver(setupSchema),
  })

  const watchedUrl = watch('url')
  const watchedUsername = watch('username')
  const watchedPassword = watch('password')
  const watchedVerify = watch('verify')
  const watchedEauth = watch('eauth')

  const canTest =
    Boolean(watchedUrl) &&
    Boolean(watchedUsername) &&
    Boolean(watchedPassword) &&
    !testMut.isPending

  async function handleTest() {
    setTestResult(null)
    setTestOk(false)
    try {
      const result = await testMut.mutateAsync({
        eauth: watchedEauth,
        password: watchedPassword,
        url: watchedUrl,
        username: watchedUsername,
        verify: watchedVerify,
      })
      setTestResult(result)
      setTestOk(result.ok)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Connection test failed'
      setTestResult({ detail: msg, ok: false })
      setTestOk(false)
    }
  }

  async function onSubmit(values: SetupFormValues) {
    setSaveError(null)
    try {
      await saveMut.mutateAsync({
        eauth: values.eauth,
        password: values.password,
        url: values.url,
        username: values.username,
        verify: values.verify,
      })
      // Seed the status cache synchronously so the SetupGuard sees
      // configured=true on the very next render and doesn't bounce us
      // back to /setup before the invalidation-driven refetch lands.
      qc.setQueryData(settingsKeys.status(), {
        configured: true,
        missing: [],
      })
      void navigate({ to: '/' })
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Save failed.')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <div className="w-full max-w-xl space-y-6 rounded-lg border border-border bg-card p-8 shadow-sm">
        <header>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            First-run setup
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">
            Connect to your salt-api
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Halite needs your salt-api URL and credentials before it can do
            anything useful. Test the connection, then save to continue.
          </p>
        </header>

        <form className="space-y-4" noValidate onSubmit={handleSubmit(onSubmit)}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="setup-url">URL</Label>
              <Input
                id="setup-url"
                autoComplete="off"
                placeholder="https://salt-master:8080"
                {...register('url')}
              />
              {errors.url && (
                <p className="text-sm text-destructive">{errors.url.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="setup-username">Username</Label>
              <Input
                id="setup-username"
                autoComplete="off"
                {...register('username')}
              />
              {errors.username && (
                <p className="text-sm text-destructive">{errors.username.message}</p>
              )}
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="setup-password">Password</Label>
              <Input
                id="setup-password"
                type="password"
                autoComplete="new-password"
                placeholder="Enter password"
                {...register('password')}
              />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="setup-eauth">Auth backend (eauth)</Label>
              <Select
                value={watchedEauth}
                onValueChange={(v) =>
                  setValue('eauth', v as SetupFormValues['eauth'], { shouldDirty: true })
                }
              >
                <SelectTrigger id="setup-eauth">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pam">pam</SelectItem>
                  <SelectItem value="sharedsecret">sharedsecret</SelectItem>
                  <SelectItem value="ldap">ldap</SelectItem>
                  <SelectItem value="file">file</SelectItem>
                  <SelectItem value="auto">auto</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex items-center justify-between rounded-md border p-3">
            <div className="space-y-0.5">
              <Label htmlFor="setup-verify" className="text-sm font-medium">
                Verify TLS
              </Label>
              <p className="text-xs text-muted-foreground">
                Disable only for self-signed certs in dev environments.
              </p>
            </div>
            <Switch
              id="setup-verify"
              checked={watchedVerify}
              onCheckedChange={(c) => setValue('verify', c, { shouldDirty: true })}
            />
          </div>

          {/* Test Connection */}
          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              variant="outline"
              disabled={!canTest}
              onClick={handleTest}
            >
              {testMut.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Test Connection
            </Button>

            {testResult !== null && (
              <span
                className={
                  testResult.ok
                    ? 'flex items-center gap-1 text-sm text-emerald-600 dark:text-emerald-400'
                    : 'flex items-center gap-1 text-sm text-destructive'
                }
              >
                {testResult.ok ? (
                  <Check className="h-4 w-4" />
                ) : (
                  <X className="h-4 w-4" />
                )}
                {testResult.ok
                  ? `Logged in (${testResult.minion_count ?? 0} minions)`
                  : testResult.detail}
              </span>
            )}
          </div>

          {/* Save */}
          <div className="flex flex-wrap items-center gap-3 border-t pt-4">
            <Button type="submit" disabled={!testOk || isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                'Save & Continue'
              )}
            </Button>

            {saveError !== null && (
              <span className="text-sm text-destructive">{saveError}</span>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}

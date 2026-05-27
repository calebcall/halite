// frontend/src/features/admin/settings-page.tsx
import { zodResolver } from '@hookform/resolvers/zod'
import { Check, Loader2, RefreshCw, X } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
import { MustChangePassword } from '@/features/auth/guards'
import type { components } from '@/shared/api/types.gen'
import { useSettings, useTestSalt, useTestSaltSaved, useUpdateLogging, useUpdatePollers, useUpdateSalt } from './use-settings'

// ─── Type aliases ────────────────────────────────────────────────────────────

type SaltSettingsOut = components['schemas']['SaltSettingsOut']
type PollerSettingsOut = components['schemas']['PollerSettingsOut']
type LoggingSettingsOut = components['schemas']['LoggingSettingsOut']
type TestSaltConnectionOut = components['schemas']['TestSaltConnectionOut']

// ─── Page shell ──────────────────────────────────────────────────────────────

export function SettingsPage() {
  return (
    <MustChangePassword>
      <SettingsPageInner />
    </MustChangePassword>
  )
}

function SettingsPageInner() {
  const { data, isLoading, isError } = useSettings()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Loading settings…
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        Failed to load settings. Check your permissions or try refreshing.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h2 className="text-2xl font-semibold tracking-tight">Settings</h2>
        <p className="text-sm text-muted-foreground">
          Configure the salt-api connection, background pollers, and logging.
          Changes apply immediately unless noted.
        </p>
      </header>

      <SaltSection initial={data.salt} />
      <PollersSection initial={data.pollers} />
      <LoggingSection initial={data.logging} />
    </div>
  )
}

// ─── Salt API section ─────────────────────────────────────────────────────────

const saltSchema = z.object({
  eauth: z.enum(['pam', 'sharedsecret', 'ldap', 'file', 'auto']),
  password: z.string(),
  url: z.string().min(1, 'URL is required'),
  username: z.string().min(1, 'Username is required'),
  verify: z.boolean(),
})

type SaltFormValues = z.infer<typeof saltSchema>

function SaltSection({ initial }: { initial: SaltSettingsOut }) {
  const updateMut = useUpdateSalt()
  const testMut = useTestSalt()
  const testSavedMut = useTestSaltSaved()
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [testResult, setTestResult] = useState<TestSaltConnectionOut | null>(null)

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<SaltFormValues>({
    defaultValues: {
      eauth: initial.eauth,
      password: '',
      url: initial.url ?? '',
      username: initial.username ?? '',
      verify: initial.verify,
    },
    resolver: zodResolver(saltSchema),
  })

  const watchedUrl = watch('url')
  const watchedUsername = watch('username')
  const watchedPassword = watch('password')
  const watchedVerify = watch('verify')
  const watchedEauth = watch('eauth')

  // Test Connection requires URL and username. Password is needed for test
  // but we can't test with a stored password (we don't have it), so require
  // the user to enter one if password_set is false; if it is set allow test
  // using stored creds by sending empty password only when it was already set.
  const canTest =
    (Boolean(watchedPassword)
      ? Boolean(watchedUrl) && Boolean(watchedUsername)
      : initial.password_set) &&
    !testMut.isPending &&
    !testSavedMut.isPending

  async function handleTest() {
    setTestResult(null)
    // If the user typed a new password, test those specific creds via the
    // body-driven endpoint. If they left it blank and the DB has stored
    // creds (password_set=true), test the stored creds via the saved
    // endpoint — we can't roundtrip the password to the form for security.
    try {
      const result = watchedPassword
        ? await testMut.mutateAsync({
            eauth: watchedEauth,
            password: watchedPassword,
            url: watchedUrl,
            username: watchedUsername,
            verify: watchedVerify,
          })
        : await testSavedMut.mutateAsync()
      setTestResult(result)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Connection test failed'
      setTestResult({ detail: msg, ok: false })
    }
  }

  async function onSubmit(values: SaltFormValues) {
    setSaveMsg(null)
    try {
      const body: Record<string, unknown> = {
        eauth: values.eauth,
        url: values.url,
        username: values.username,
        verify: values.verify,
      }
      // Only include password if the user typed something
      if (values.password.length > 0) {
        body.password = values.password
      }
      await updateMut.mutateAsync(body as Parameters<typeof updateMut.mutateAsync>[0])
      setSaveMsg({ ok: true, text: 'Salt settings saved.' })
    } catch (e) {
      setSaveMsg({ ok: false, text: e instanceof Error ? e.message : 'Save failed.' })
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Salt API</CardTitle>
        <CardDescription>
          Connection details for the salt-api endpoint. Halite talks to this
          service to query minions, run jobs, and manage keys.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" noValidate onSubmit={handleSubmit(onSubmit)}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="salt-url">URL</Label>
              <Input
                id="salt-url"
                autoComplete="off"
                placeholder="https://salt-master:8080"
                {...register('url')}
              />
              {errors.url && (
                <p className="text-sm text-destructive">{errors.url.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="salt-username">Username</Label>
              <Input
                id="salt-username"
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
              <Label htmlFor="salt-password">Password</Label>
              <Input
                id="salt-password"
                type="password"
                autoComplete="new-password"
                placeholder={initial.password_set ? '•••••• (set)' : 'Enter password'}
                {...register('password')}
              />
              <p className="text-xs text-muted-foreground">
                {initial.password_set
                  ? 'Leave blank to keep the existing password.'
                  : 'Password has not been set.'}
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="salt-eauth">Auth backend (eauth)</Label>
              <Select
                value={watchedEauth}
                onValueChange={(v) =>
                  setValue('eauth', v as SaltFormValues['eauth'], { shouldDirty: true })
                }
              >
                <SelectTrigger id="salt-eauth">
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
              <Label htmlFor="salt-verify" className="text-sm font-medium">
                Verify TLS
              </Label>
              <p className="text-xs text-muted-foreground">
                Disable only for self-signed certs in dev environments.
              </p>
            </div>
            <Switch
              id="salt-verify"
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
              {testMut.isPending || testSavedMut.isPending ? (
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
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                'Save'
              )}
            </Button>

            {saveMsg !== null && (
              <span
                className={
                  saveMsg.ok
                    ? 'text-sm text-emerald-600 dark:text-emerald-400'
                    : 'text-sm text-destructive'
                }
              >
                {saveMsg.text}
              </span>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

// ─── Pollers section ──────────────────────────────────────────────────────────

const pollersSchema = z.object({
  fleet_poll_interval_seconds: z.coerce.number().int().min(0),
  inventory_refresh_initial_delay_s: z.coerce.number().int().min(0),
  inventory_refresh_minutes: z.coerce.number().int().min(0),
  minion_state_grains_interval_seconds: z.coerce.number().int().min(0),
  minion_state_initial_delay_seconds: z.coerce.number().int().min(0),
  minion_state_keys_interval_seconds: z.coerce.number().int().min(0),
  minion_state_presence_interval_seconds: z.coerce.number().int().min(0),
})

type PollersFormValues = z.infer<typeof pollersSchema>

type PollerField = {
  help: string
  id: keyof PollersFormValues
  label: string
}

const POLLER_FIELDS: PollerField[] = [
  {
    help: '0 disables. Touches every minion — leave off unless you need package inventory.',
    id: 'inventory_refresh_minutes',
    label: 'Inventory refresh (minutes)',
  },
  {
    help: 'Wait this long after startup before the first inventory run.',
    id: 'inventory_refresh_initial_delay_s',
    label: 'Inventory initial delay (seconds)',
  },
  {
    help: '0 disables. Heavy — sequential list_job calls per recent jid. Use a high value or disable.',
    id: 'fleet_poll_interval_seconds',
    label: 'Fleet highstate poll (seconds)',
  },
  {
    help: '0 disables. Recommended: 300.',
    id: 'minion_state_keys_interval_seconds',
    label: 'Minion keys refresh (seconds)',
  },
  {
    help: '0 disables. Recommended: 60.',
    id: 'minion_state_presence_interval_seconds',
    label: 'Minion presence refresh (seconds)',
  },
  {
    help: '0 disables. Recommended: 300.',
    id: 'minion_state_grains_interval_seconds',
    label: 'Minion grains refresh (seconds)',
  },
  {
    help: 'Wait this long after startup before starting minion state pollers.',
    id: 'minion_state_initial_delay_seconds',
    label: 'Minion initial delay (seconds)',
  },
]

function PollersSection({ initial }: { initial: PollerSettingsOut }) {
  const updateMut = useUpdatePollers()
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PollersFormValues>({
    defaultValues: {
      fleet_poll_interval_seconds: initial.fleet_poll_interval_seconds,
      inventory_refresh_initial_delay_s: initial.inventory_refresh_initial_delay_s,
      inventory_refresh_minutes: initial.inventory_refresh_minutes,
      minion_state_grains_interval_seconds: initial.minion_state_grains_interval_seconds,
      minion_state_initial_delay_seconds: initial.minion_state_initial_delay_seconds,
      minion_state_keys_interval_seconds: initial.minion_state_keys_interval_seconds,
      minion_state_presence_interval_seconds: initial.minion_state_presence_interval_seconds,
    },
    resolver: zodResolver(pollersSchema),
  })

  async function onSubmit(values: PollersFormValues) {
    setSaveMsg(null)
    try {
      await updateMut.mutateAsync(values)
      setSaveMsg({ ok: true, text: 'Poller settings saved.' })
    } catch (e) {
      setSaveMsg({ ok: false, text: e instanceof Error ? e.message : 'Save failed.' })
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pollers</CardTitle>
        <CardDescription>
          Background tasks that keep minion state in sync. All intervals are in
          seconds or minutes. Set to 0 to disable.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" noValidate onSubmit={handleSubmit(onSubmit)}>
          <div className="grid gap-4 sm:grid-cols-2">
            {POLLER_FIELDS.map((field) => (
              <div key={field.id} className="space-y-1.5">
                <Label htmlFor={`poller-${field.id}`}>{field.label}</Label>
                <Input
                  id={`poller-${field.id}`}
                  type="number"
                  min={0}
                  step={1}
                  {...register(field.id)}
                />
                <p className="text-xs text-muted-foreground">{field.help}</p>
                {errors[field.id] && (
                  <p className="text-sm text-destructive">{errors[field.id]?.message}</p>
                )}
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t pt-4">
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                'Save'
              )}
            </Button>

            {saveMsg !== null && (
              <span
                className={
                  saveMsg.ok
                    ? 'text-sm text-emerald-600 dark:text-emerald-400'
                    : 'text-sm text-destructive'
                }
              >
                {saveMsg.text}
              </span>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

// ─── Logging section ──────────────────────────────────────────────────────────

const loggingSchema = z.object({
  log_format: z.enum(['json', 'text']),
})

type LoggingFormValues = z.infer<typeof loggingSchema>

function LoggingSection({ initial }: { initial: LoggingSettingsOut }) {
  const updateMut = useUpdateLogging()
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null)

  const { watch, setValue, handleSubmit, formState: { isSubmitting } } = useForm<LoggingFormValues>({
    defaultValues: {
      log_format: initial.log_format,
    },
    resolver: zodResolver(loggingSchema),
  })

  const watchedFormat = watch('log_format')

  async function onSubmit(values: LoggingFormValues) {
    setSaveMsg(null)
    try {
      await updateMut.mutateAsync(values)
      setSaveMsg({ ok: true, text: 'Logging settings saved.' })
    } catch (e) {
      setSaveMsg({ ok: false, text: e instanceof Error ? e.message : 'Save failed.' })
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Logging</CardTitle>
        <CardDescription>
          Application log format. Changes take effect after a container restart.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" noValidate onSubmit={handleSubmit(onSubmit)}>
          <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-800/40 dark:bg-amber-900/20 dark:text-amber-400">
            Container restart required for log format changes to take effect.
          </div>

          <div className="space-y-2">
            <Label htmlFor="log-format">Log format</Label>
            <Select
              value={watchedFormat}
              onValueChange={(v) =>
                setValue('log_format', v as LoggingFormValues['log_format'], { shouldDirty: true })
              }
            >
              <SelectTrigger id="log-format" className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="json">json</SelectItem>
                <SelectItem value="text">text</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Use <code>json</code> for structured log aggregation (Loki, Datadog, etc.) and{' '}
              <code>text</code> for human-readable output.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t pt-4">
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                'Save'
              )}
            </Button>

            {saveMsg !== null && (
              <span
                className={
                  saveMsg.ok
                    ? 'text-sm text-emerald-600 dark:text-emerald-400'
                    : 'text-sm text-destructive'
                }
              >
                {saveMsg.text}
              </span>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  )
}


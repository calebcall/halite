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

function PollerGroup({
  title,
  description,
  enabled,
  onEnabledChange,
  children,
}: {
  title: string
  description: string
  enabled: boolean
  onEnabledChange: (v: boolean) => void
  children: React.ReactNode
}) {
  return (
    <section className="rounded-md border border-border p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-0.5">
          <h3 className="text-sm font-medium">{title}</h3>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
        <Switch checked={enabled} onCheckedChange={onEnabledChange} aria-label={`${title} enabled`} />
      </div>
      {enabled && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">{children}</div>
      )}
    </section>
  )
}


function PollerField({
  id,
  label,
  help,
  disabled,
  register,
  error,
}: {
  id: keyof PollersFormValues
  label: string
  help: string
  disabled: boolean
  register: ReturnType<typeof useForm<PollersFormValues>>['register']
  error: string | undefined
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={`poller-${id}`} className="text-xs">{label}</Label>
      <Input
        id={`poller-${id}`}
        type="number"
        min={1}
        step={1}
        disabled={disabled}
        className="h-8"
        {...register(id)}
      />
      <p className="text-xs text-muted-foreground">{help}</p>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}


const pollersSchema = z.object({
  fleet_poll_interval_seconds: z.coerce.number().int().min(1),
  inventory_refresh_initial_delay_s: z.coerce.number().int().min(0),
  inventory_refresh_minutes: z.coerce.number().int().min(1),
  jobs_poll_interval_seconds: z.coerce.number().int().min(1),
  minion_state_grains_interval_seconds: z.coerce.number().int().min(1),
  minion_state_initial_delay_seconds: z.coerce.number().int().min(0),
  minion_state_keys_interval_seconds: z.coerce.number().int().min(1),
  minion_state_presence_interval_seconds: z.coerce.number().int().min(1),
  event_stream_retention_days: z.coerce.number().int().min(1).max(365),
})

type PollersFormValues = z.infer<typeof pollersSchema>

// Defaults applied when a poller group is enabled but its interval has
// never been set (or was zeroed by a previous disable). Match what the
// backend's AppSettings model treats as sensible defaults.
const POLLER_DEFAULTS = {
  fleet_poll_interval_seconds: 600,
  inventory_refresh_initial_delay_s: 30,
  inventory_refresh_minutes: 30,
  jobs_poll_interval_seconds: 300,
  minion_state_grains_interval_seconds: 300,
  minion_state_initial_delay_seconds: 10,
  minion_state_keys_interval_seconds: 300,
  minion_state_presence_interval_seconds: 60,
  event_stream_retention_days: 30, // matches DB column default
} as const


function PollersSection({ initial }: { initial: PollerSettingsOut }) {
  const updateMut = useUpdatePollers()
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null)

  // Each group's toggle. Default to ON when any of its intervals is nonzero.
  const [enabled, setEnabled] = useState({
    fleet: initial.fleet_poll_interval_seconds > 0,
    inventory: initial.inventory_refresh_minutes > 0,
    jobs: initial.jobs_poll_interval_seconds > 0,
    minionState:
      initial.minion_state_keys_interval_seconds > 0 ||
      initial.minion_state_presence_interval_seconds > 0 ||
      initial.minion_state_grains_interval_seconds > 0,
    eventStream: initial.event_stream_enabled,
  })

  // The form holds the DESIRED interval values. When a group is toggled off
  // we DON'T zero the form field — we just send 0 to the backend at submit
  // time. That way toggling off → on doesn't lose the user's last interval.
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PollersFormValues>({
    defaultValues: {
      fleet_poll_interval_seconds:
        initial.fleet_poll_interval_seconds || POLLER_DEFAULTS.fleet_poll_interval_seconds,
      inventory_refresh_initial_delay_s:
        initial.inventory_refresh_initial_delay_s || POLLER_DEFAULTS.inventory_refresh_initial_delay_s,
      inventory_refresh_minutes:
        initial.inventory_refresh_minutes || POLLER_DEFAULTS.inventory_refresh_minutes,
      jobs_poll_interval_seconds:
        initial.jobs_poll_interval_seconds || POLLER_DEFAULTS.jobs_poll_interval_seconds,
      minion_state_grains_interval_seconds:
        initial.minion_state_grains_interval_seconds || POLLER_DEFAULTS.minion_state_grains_interval_seconds,
      minion_state_initial_delay_seconds:
        initial.minion_state_initial_delay_seconds || POLLER_DEFAULTS.minion_state_initial_delay_seconds,
      minion_state_keys_interval_seconds:
        initial.minion_state_keys_interval_seconds || POLLER_DEFAULTS.minion_state_keys_interval_seconds,
      minion_state_presence_interval_seconds:
        initial.minion_state_presence_interval_seconds || POLLER_DEFAULTS.minion_state_presence_interval_seconds,
      event_stream_retention_days:
        initial.event_stream_retention_days || POLLER_DEFAULTS.event_stream_retention_days,
    },
    resolver: zodResolver(pollersSchema),
  })

  async function onSubmit(values: PollersFormValues) {
    setSaveMsg(null)
    // Mask out disabled groups before sending. The interval inputs stay
    // intact in the form so toggling back on restores the user's value.
    const payload = {
      fleet_poll_interval_seconds: enabled.fleet ? values.fleet_poll_interval_seconds : 0,
      inventory_refresh_initial_delay_s: values.inventory_refresh_initial_delay_s,
      inventory_refresh_minutes: enabled.inventory ? values.inventory_refresh_minutes : 0,
      jobs_poll_interval_seconds: enabled.jobs ? values.jobs_poll_interval_seconds : 0,
      minion_state_grains_interval_seconds:
        enabled.minionState ? values.minion_state_grains_interval_seconds : 0,
      minion_state_initial_delay_seconds: values.minion_state_initial_delay_seconds,
      minion_state_keys_interval_seconds:
        enabled.minionState ? values.minion_state_keys_interval_seconds : 0,
      minion_state_presence_interval_seconds:
        enabled.minionState ? values.minion_state_presence_interval_seconds : 0,
      event_stream_enabled: enabled.eventStream,
      event_stream_retention_days: values.event_stream_retention_days,
    }
    try {
      await updateMut.mutateAsync(payload)
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
          Background tasks that keep minion state, jobs, and highstate runs in
          sync. Toggle each group on/off; intervals are remembered when you
          toggle off so you don't have to re-enter them.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" noValidate onSubmit={handleSubmit(onSubmit)}>
          <PollerGroup
            title="Minion state"
            description="Keeps the minion list current (key status, online/offline, grains)."
            enabled={enabled.minionState}
            onEnabledChange={(v) => setEnabled((e) => ({ ...e, minionState: v }))}
          >
            <PollerField
              id="minion_state_keys_interval_seconds"
              label="Keys refresh (seconds)"
              help="How often to reconcile against wheel.key.list_all. Recommended: 300."
              disabled={!enabled.minionState}
              register={register}
              error={errors.minion_state_keys_interval_seconds?.message}
            />
            <PollerField
              id="minion_state_presence_interval_seconds"
              label="Presence refresh (seconds)"
              help="manage.present check — drives online/offline. Recommended: 60."
              disabled={!enabled.minionState}
              register={register}
              error={errors.minion_state_presence_interval_seconds?.message}
            />
            <PollerField
              id="minion_state_grains_interval_seconds"
              label="Grains refresh (seconds)"
              help="cache.grains fetch (master-side, no minion contact). Recommended: 300."
              disabled={!enabled.minionState}
              register={register}
              error={errors.minion_state_grains_interval_seconds?.message}
            />
            <PollerField
              id="minion_state_initial_delay_seconds"
              label="Initial delay (seconds)"
              help="Wait this long after app startup before the first tick."
              disabled={!enabled.minionState}
              register={register}
              error={errors.minion_state_initial_delay_seconds?.message}
            />
          </PollerGroup>

          <PollerGroup
            title="Jobs index"
            description="Populates the overview metrics + timeline by polling runner.jobs.list_jobs."
            enabled={enabled.jobs}
            onEnabledChange={(v) => setEnabled((e) => ({ ...e, jobs: v }))}
          >
            <PollerField
              id="jobs_poll_interval_seconds"
              label="Poll interval (seconds)"
              help="Recommended: 300. Overview reads from DB so polling more often gains little."
              disabled={!enabled.jobs}
              register={register}
              error={errors.jobs_poll_interval_seconds?.message}
            />
          </PollerGroup>

          <PollerGroup
            title="Fleet highstate ingest"
            description="Persists highstate results per minion+jid. Heavy — fires one runner.jobs.list_job call per recent jid."
            enabled={enabled.fleet}
            onEnabledChange={(v) => setEnabled((e) => ({ ...e, fleet: v }))}
          >
            <PollerField
              id="fleet_poll_interval_seconds"
              label="Poll interval (seconds)"
              help="Recommended: 600 or higher. Disable if your master can't handle the load."
              disabled={!enabled.fleet}
              register={register}
              error={errors.fleet_poll_interval_seconds?.message}
            />
          </PollerGroup>

          <PollerGroup
            title="Inventory (packages)"
            description="Runs pkg.list_pkgs across the fleet. Touches every minion — leave off unless you need it."
            enabled={enabled.inventory}
            onEnabledChange={(v) => setEnabled((e) => ({ ...e, inventory: v }))}
          >
            <PollerField
              id="inventory_refresh_minutes"
              label="Refresh interval (minutes)"
              help="Recommended: 30 or more."
              disabled={!enabled.inventory}
              register={register}
              error={errors.inventory_refresh_minutes?.message}
            />
            <PollerField
              id="inventory_refresh_initial_delay_s"
              label="Initial delay (seconds)"
              help="Wait this long after app startup before the first run."
              disabled={!enabled.inventory}
              register={register}
              error={errors.inventory_refresh_initial_delay_s?.message}
            />
          </PollerGroup>

          <section className="rounded-md border border-border p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-0.5">
                <h3 className="text-sm font-medium">Event stream</h3>
                <p className="text-xs text-muted-foreground">
                  Captures live Salt event bus activity. When enabled, events are stored and exposed via the Activity page and SSE stream.
                </p>
              </div>
              <Switch
                checked={enabled.eventStream}
                onCheckedChange={(v) => setEnabled((e) => ({ ...e, eventStream: v }))}
                aria-label="Event stream enabled"
              />
            </div>
            {enabled.eventStream && (
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <PollerField
                  id="event_stream_retention_days"
                  label="Retention (days)"
                  help="Events older than this are pruned automatically. Min 1, max 365."
                  disabled={!enabled.eventStream}
                  register={register}
                  error={errors.event_stream_retention_days?.message}
                />
              </div>
            )}
          </section>

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


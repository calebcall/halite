// frontend/src/features/jobs/job-detail-page.tsx
import { Link, useParams } from '@tanstack/react-router'
import { ArrowLeft, CheckCircle2, ChevronDown, Loader2, Terminal, XCircle } from 'lucide-react'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ApiError } from '@/shared/api/client'
import { MustChangePassword } from '@/features/auth/guards'
import { useHasPerm } from '@/features/auth/use-has-perm'
import type { JobMinionResult } from './api'
import { useJob } from './use-jobs'

export function JobDetailPage() {
  return (
    <MustChangePassword>
      <JobDetailPageInner />
    </MustChangePassword>
  )
}

function JobDetailPageInner() {
  const { jid } = useParams({ from: '/app/jobs/$jid' })
  const { data, isPending, error } = useJob(jid)
  const canRun = useHasPerm('execute', 'salt:*')

  if (isPending) {
    return (
      <div className="flex h-40 items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    )
  }
  if (error instanceof ApiError && error.status === 404) {
    return (
      <div className="flex flex-col gap-3">
        <BackToList />
        <div className="rounded-md border border-amber-400/40 bg-amber-50 p-6 text-sm text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
          Job <code className="font-mono">{jid}</code> is not in the master cache. Salt expires jobs after the configured <code>keep_jobs</code> window.
        </div>
      </div>
    )
  }
  if (error instanceof ApiError && error.isForbidden) {
    return (
      <div className="flex flex-col gap-3">
        <BackToList />
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
          You don&apos;t have permission to view this job.
        </div>
      </div>
    )
  }
  if (error instanceof ApiError && error.status === 503) {
    return (
      <div className="flex flex-col gap-3">
        <BackToList />
        <div className="rounded-md border border-amber-400/40 bg-amber-50 p-6 text-sm text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
          Salt-API is not configured. Set <code>SALT_API_URL</code>, <code>SALT_API_USERNAME</code>, and <code>SALT_API_PASSWORD</code> in your <code>.env</code> and restart the stack.
        </div>
      </div>
    )
  }
  if (!data) {
    return null
  }

  return (
    <div className="flex flex-col gap-4">
      <BackToList />
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight font-mono">{data.jid}</h2>
          <p className="text-sm text-muted-foreground">{data.function} on {data.target || 'no target'}</p>
        </div>
        {canRun && (
          <Button asChild variant="outline" size="sm">
            <Link
              to="/run"
              search={{
                target: data.target,
                target_type: data.target_type || 'glob',
                fun: data.function,
                args: data.arguments.length > 0 ? JSON.stringify(data.arguments) : undefined,
                kwargs: Object.keys(data.kwargs as Record<string, unknown>).length > 0 ? JSON.stringify(data.kwargs) : undefined,
              }}
            >
              <Terminal className="mr-2 h-4 w-4" />
              Run again
            </Link>
          </Button>
        )}
      </header>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 rounded-md border bg-muted/20 p-4 text-sm sm:grid-cols-4">
        <Field label="Function" value={data.function} mono />
        <Field label="Target" value={data.target || '—'} mono />
        <Field label="Target type" value={data.target_type || '—'} />
        <Field label="User" value={data.user || '—'} />
        <Field label="Started" value={data.start_time || '—'} />
        <Field label="Minions" value={String(data.minions.length)} />
      </dl>

      {data.arguments.length > 0 && (
        <div className="rounded-md border p-4">
          <p className="mb-2 text-sm font-medium">Arguments</p>
          <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">
            {JSON.stringify(data.arguments, null, 2)}
          </pre>
        </div>
      )}

      {Object.keys(data.kwargs).length > 0 && (
        <div className="rounded-md border p-4">
          <p className="mb-2 text-sm font-medium">Keyword arguments</p>
          <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">
            {JSON.stringify(data.kwargs, null, 2)}
          </pre>
        </div>
      )}

      <div className="flex flex-col gap-2">
        <h3 className="text-lg font-semibold tracking-tight">Results</h3>
        {data.results.length === 0 ? (
          <p className="text-sm text-muted-foreground">No results yet — the job may still be running.</p>
        ) : (
          data.results.map((r) => <MinionResultCard key={r.minion} result={r} />)
        )}
      </div>
    </div>
  )
}

function BackToList() {
  return (
    <Link to="/jobs" className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft className="h-3.5 w-3.5" />
      All jobs
    </Link>
  )
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex flex-col">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={mono ? 'font-mono text-xs' : 'text-sm'}>{value}</dd>
    </div>
  )
}

function MinionResultCard({ result }: { result: JobMinionResult }) {
  const [open, setOpen] = useState(false)
  const panelId = `minion-result-${result.minion}`
  const ok = result.success === true
  const failed = result.success === false
  return (
    <div className="rounded-md border">
      <Button
        type="button"
        variant="ghost"
        className="flex h-auto w-full items-center justify-between gap-2 rounded-none px-4 py-3 text-left"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
      >
        <div className="flex items-center gap-3">
          {ok && <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />}
          {failed && <XCircle className="h-4 w-4 text-destructive" />}
          <span className="font-mono text-sm">{result.minion}</span>
          {ok && <Badge className="bg-emerald-100 text-emerald-900 hover:bg-emerald-100 dark:bg-emerald-950/40 dark:text-emerald-200">success</Badge>}
          {failed && <Badge variant="destructive">failed</Badge>}
          {result.retcode !== null && result.retcode !== undefined && (
            <span className="text-xs text-muted-foreground">retcode {result.retcode}</span>
          )}
        </div>
        <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
      </Button>
      <pre
        id={panelId}
        hidden={!open}
        className="overflow-x-auto border-t bg-muted/20 p-4 text-xs"
      >
        {JSON.stringify(result.return_value, null, 2)}
      </pre>
    </div>
  )
}

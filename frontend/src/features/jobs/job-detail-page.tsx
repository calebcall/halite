// frontend/src/features/jobs/job-detail-page.tsx
import { Link, useParams } from '@tanstack/react-router'
import { ArrowLeft, CheckCircle2, ChevronDown, Loader2, Lock, Square, Terminal, XCircle } from 'lucide-react'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { ApiError, errorDetail } from '@/shared/api/client'
import { MustChangePassword } from '@/features/auth/guards'
import { useHasPerm } from '@/features/auth/use-has-perm'
import type { JobMinionResult } from './api'
import { KillJobDialog } from './kill-job-dialog'
import { useJob } from './use-jobs'
import { HighstateResult } from './highstate/highstate-result'
import { JobHighstateSummary } from './highstate/job-highstate-summary'
import { isBlockedReturn, minionHasFailures, summarizeJobHighstate } from './highstate/job-summary'
import { parseHighstate } from './highstate/parse'

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
  const canKill = useHasPerm('kill', 'job:*')
  const [killOpen, setKillOpen] = useState(false)
  const [failuresOnly, setFailuresOnly] = useState(false)
  const detail = errorDetail(error)

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
        <div className="rounded-md border border-warning/40 bg-warning/10 p-6 text-sm text-foreground">
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
        <div className="rounded-md border border-warning/40 bg-warning/10 p-6 text-sm text-foreground">
          <p>Salt-API is not configured. Set <code>SALT_API_URL</code>, <code>SALT_API_USERNAME</code>, and <code>SALT_API_PASSWORD</code> in your <code>.env</code> and restart the stack.</p>
          {detail && <p className="mt-2 font-mono text-xs">{detail}</p>}
        </div>
      </div>
    )
  }
  if (error instanceof ApiError && error.status === 502) {
    return (
      <div className="flex flex-col gap-3">
        <BackToList />
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
          <p>Salt-API responded with an error.</p>
          {detail && <p className="mt-2 font-mono text-xs">{detail}</p>}
        </div>
      </div>
    )
  }
  if (!data) {
    return null
  }

  const isRunning = data.results.length < data.minions.length
  const jobHighstate = summarizeJobHighstate(data.results)

  return (
    <div className="flex flex-col gap-4">
      <BackToList />
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight font-mono">{data.jid}</h2>
          <p className="text-sm text-muted-foreground">{data.function} on {data.target || 'no target'}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canKill && isRunning && (
            <Button
              variant="outline"
              size="sm"
              className="text-destructive hover:text-destructive"
              onClick={() => setKillOpen(true)}
            >
              <Square className="mr-2 h-4 w-4 fill-current" />
              Kill job
            </Button>
          )}
          {canRun && (
            <Button asChild variant="outline" size="sm">
              <Link
                to="/run"
                search={{
                  target: data.target,
                  target_type: data.target_type || 'glob',
                  fun: data.function,
                  args: data.arguments.length > 0 ? JSON.stringify(data.arguments) : undefined,
                  kwargs: Object.keys(data.kwargs ?? {}).length > 0 ? JSON.stringify(data.kwargs) : undefined,
                }}
              >
                <Terminal className="mr-2 h-4 w-4" />
                Run again
              </Link>
            </Button>
          )}
        </div>
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

      {Object.keys(data.kwargs ?? {}).length > 0 && (
        <div className="rounded-md border p-4">
          <p className="mb-2 text-sm font-medium">Keyword arguments</p>
          <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">
            {JSON.stringify(data.kwargs, null, 2)}
          </pre>
        </div>
      )}

      {jobHighstate && (
        <JobHighstateSummary stats={jobHighstate} />
      )}

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-lg font-semibold tracking-tight">Results</h3>
          {jobHighstate && jobHighstate.minionsWithFailures > 0 && (
            <div className="flex items-center gap-2">
              <Switch
                id="failures-only"
                checked={failuresOnly}
                onCheckedChange={setFailuresOnly}
              />
              <Label htmlFor="failures-only" className="text-sm">Show failures only</Label>
            </div>
          )}
        </div>
        {data.results.length === 0 ? (
          <p className="text-sm text-muted-foreground">No results yet — the job may still be running.</p>
        ) : (
          <>
            {data.results
              .filter((r) => !failuresOnly || minionHasFailures(r))
              .map((r) => (
                <MinionResultCard key={r.minion} result={r} failuresOnly={failuresOnly} />
              ))}
            {failuresOnly && data.results.every((r) => !minionHasFailures(r)) && (
              <p className="text-sm text-muted-foreground italic">All minions succeeded — toggle the filter to see them.</p>
            )}
          </>
        )}
      </div>

      <KillJobDialog
        jid={data.jid}
        jobFunction={data.function}
        jobTarget={data.target}
        open={killOpen}
        onOpenChange={setKillOpen}
      />
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

function MinionResultCard({
  result,
  failuresOnly = false,
}: {
  result: JobMinionResult
  failuresOnly?: boolean
}) {
  const [open, setOpen] = useState(false)
  const panelId = `minion-result-${result.minion}`
  const blocked = isBlockedReturn(result.return_value)
  const ok = result.success === true && !blocked
  const failed = result.success === false && !blocked
  const highstate = parseHighstate(result.return_value)
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
          {ok && <CheckCircle2 className="h-4 w-4 text-success" />}
          {failed && <XCircle className="h-4 w-4 text-destructive" />}
          {blocked && <Lock className="h-4 w-4 text-warning" />}
          <span className="font-mono text-sm">{result.minion}</span>
          {ok && <Badge variant="success">success</Badge>}
          {failed && <Badge variant="destructive">failed</Badge>}
          {blocked && <Badge variant="warning">blocked</Badge>}
          {result.retcode !== null && result.retcode !== undefined && (
            <span className="text-xs text-muted-foreground">retcode {result.retcode}</span>
          )}
        </div>
        <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
      </Button>
      <div
        id={panelId}
        hidden={!open}
        className="border-t bg-muted/20"
      >
        {highstate ? (
          <HighstateResult states={highstate} filterFailures={failuresOnly} />
        ) : (
          <pre className="overflow-x-auto p-4 text-xs">
            {JSON.stringify(result.return_value, null, 2)}
          </pre>
        )}
      </div>
    </div>
  )
}

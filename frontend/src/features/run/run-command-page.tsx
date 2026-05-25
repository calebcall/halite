// frontend/src/features/run/run-command-page.tsx
import { useNavigate, useSearch } from '@tanstack/react-router'
import { Loader2, Terminal } from 'lucide-react'
import { useState } from 'react'

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
import { Textarea } from '@/components/ui/textarea'
import { MustChangePassword } from '@/features/auth/guards'
import { ApiError, errorDetail } from '@/shared/api/client'

import { useRunCommand } from './use-run'

const TARGET_TYPES = ['glob', 'list', 'pcre', 'grain', 'nodegroup', 'compound'] as const

function parseSearchArgs(raw: string | undefined): string {
  if (!raw) return ''
  try {
    const parsed = JSON.parse(raw) as unknown
    if (Array.isArray(parsed)) {
      return parsed.map((v) => (typeof v === 'string' ? v : JSON.stringify(v))).join('\n')
    }
  } catch {
    // fall through
  }
  return ''
}

function parseSearchKwargs(raw: string | undefined): string {
  if (!raw) return ''
  try {
    const parsed = JSON.parse(raw) as unknown
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return Object.entries(parsed as Record<string, unknown>)
        .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
        .join('\n')
    }
  } catch {
    // fall through
  }
  return ''
}

export function RunCommandPage() {
  return (
    <MustChangePassword>
      <RunCommandPageInner />
    </MustChangePassword>
  )
}

function RunCommandPageInner() {
  const navigate = useNavigate()
  const mutation = useRunCommand()
  const search = useSearch({ from: '/app/run' })

  const initialTarget = search.target || '*'
  const initialTargetType = (
    TARGET_TYPES.includes(search.target_type as never) ? search.target_type : 'glob'
  ) as (typeof TARGET_TYPES)[number]
  const initialFun = search.fun || ''
  const initialArgs = parseSearchArgs(search.args)
  const initialKwargs = parseSearchKwargs(search.kwargs)

  const [target, setTarget] = useState(initialTarget)
  const [targetType, setTargetType] = useState<(typeof TARGET_TYPES)[number]>(initialTargetType)
  const [fun, setFun] = useState(initialFun)
  const [argsText, setArgsText] = useState(initialArgs)
  const [kwargsText, setKwargsText] = useState(initialKwargs)
  const [error, setError] = useState<string | null>(null)

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)
    const args = argsText.split('\n').map((s) => s.trim()).filter((s) => s.length > 0)
    const kwargs: Record<string, unknown> = {}
    for (const line of kwargsText.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed) continue
      const eq = trimmed.indexOf('=')
      if (eq === -1) {
        setError(`Invalid kwarg line (expected key=value): ${trimmed}`)
        return
      }
      const key = trimmed.slice(0, eq).trim()
      const rawValue = trimmed.slice(eq + 1).trim()
      // Try to parse as JSON so dicts / arrays / bools / numbers round-trip
      // through the textarea. If it doesn't parse, treat as plain string.
      let value: unknown = rawValue
      try {
        value = JSON.parse(rawValue)
      } catch {
        // Not JSON — keep as raw string
      }
      kwargs[key] = value
    }
    mutation.mutate(
      { target, target_type: targetType, fun, args, kwargs },
      {
        onSuccess: (out) => {
          if (out.jid) {
            void navigate({ to: '/jobs/$jid', params: { jid: out.jid } })
          } else {
            setError('Salt returned no jid')
          }
        },
        onError: (e) => {
          if (e instanceof ApiError && e.isForbidden) {
            setError('You don’t have permission to run salt commands.')
          } else if (e instanceof ApiError && e.status === 422) {
            const detail = (e.body as { detail?: unknown })?.detail
            setError(typeof detail === 'string' ? detail : 'Invalid input.')
          } else if (e instanceof ApiError && e.status === 502) {
            const detail = errorDetail(e)
            setError(detail ? `Salt-API returned an error: ${detail}` : 'Salt-API returned an error.')
          } else if (e instanceof ApiError && e.status === 503) {
            const detail = errorDetail(e)
            setError(detail ? `Salt-API is not reachable: ${detail}` : 'Salt-API is not reachable.')
          } else {
            setError(e instanceof Error ? e.message : 'Run failed.')
          }
        },
      },
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-center gap-3">
        <Terminal className="h-6 w-6 text-muted-foreground" />
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Run command</h2>
          <p className="text-sm text-muted-foreground">
            Fire a salt execution module function and watch the results on the job page.
          </p>
        </div>
      </header>

      <form className="grid max-w-2xl gap-4 rounded-md border p-4" onSubmit={onSubmit}>
        <div className="grid gap-2">
          <Label htmlFor="target">Target</Label>
          <Input
            id="target"
            required
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="* or web-* or web-01"
            className="font-mono"
          />
        </div>

        <div className="grid gap-2">
          <Label htmlFor="target_type">Target type</Label>
          <Select value={targetType} onValueChange={(v) => setTargetType(v as typeof targetType)}>
            <SelectTrigger id="target_type" className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TARGET_TYPES.map((t) => (
                <SelectItem key={t} value={t}>{t}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="grid gap-2">
          <Label htmlFor="fun">Function</Label>
          <Input
            id="fun"
            required
            value={fun}
            onChange={(e) => setFun(e.target.value)}
            placeholder="e.g. test.ping or cmd.run"
            className="font-mono"
          />
        </div>

        <div className="grid gap-2">
          <Label htmlFor="args">Arguments (one per line, optional)</Label>
          <Textarea
            id="args"
            rows={3}
            value={argsText}
            onChange={(e) => setArgsText(e.target.value)}
            placeholder="ls /tmp"
            className="font-mono text-sm"
          />
        </div>

        <div className="grid gap-2">
          <Label htmlFor="kwargs">Keyword arguments (key=value, one per line, optional)</Label>
          <Textarea
            id="kwargs"
            rows={3}
            value={kwargsText}
            onChange={(e) => setKwargsText(e.target.value)}
            placeholder="pillar={}"
            className="font-mono text-sm"
          />
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <div className="flex justify-end">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {mutation.isPending ? 'Running…' : 'Run'}
          </Button>
        </div>
      </form>
    </div>
  )
}

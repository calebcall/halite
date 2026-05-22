// frontend/src/features/minions/minion-detail-page.tsx
import { ArrowLeft, Loader2, Server } from 'lucide-react'
import { Link, useParams } from '@tanstack/react-router'
import { useMemo, useState } from 'react'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ApiError } from '@/shared/api/client'
import { MustChangePassword } from '@/features/auth/guards'
import { StatusBadge } from './minions-list-page'
import { useMinion } from './use-minions'

export function MinionDetailPage() {
  return (
    <MustChangePassword>
      <MinionDetailPageInner />
    </MustChangePassword>
  )
}

function MinionDetailPageInner() {
  const { minionId } = useParams({ from: '/app/minions/$minionId' })
  const { data, isPending, error } = useMinion(minionId)
  const [grainSearch, setGrainSearch] = useState('')

  if (error instanceof ApiError && error.status === 404) {
    return <NotFoundPanel minionId={minionId} />
  }
  if (error instanceof ApiError && error.isForbidden) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        You don&apos;t have permission to view minions.
      </div>
    )
  }
  if (error instanceof ApiError && error.status === 503) {
    return (
      <div className="rounded-md border border-amber-400/40 bg-amber-50 p-6 text-sm text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
        Salt-API is not configured.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <Link to="/minions" className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:underline">
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to minions
      </Link>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Server className="h-6 w-6 text-muted-foreground" />
          <h2 className="font-mono text-2xl font-semibold tracking-tight">{minionId}</h2>
          {data && <StatusBadge status={data.status} />}
        </div>
      </div>

      {isPending && (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      )}

      {data && (
        <>
          <dl className="grid grid-cols-2 gap-2 rounded-md border p-4 text-sm">
            <dt className="text-muted-foreground">IP address</dt>
            <dd className="font-mono">{data.ip ?? '—'}</dd>
            <dt className="text-muted-foreground">Status</dt>
            <dd>{data.status}</dd>
          </dl>

          {data.status !== 'online' && (
            <div className="rounded-md border border-muted bg-muted/30 p-4 text-sm text-muted-foreground">
              Grains are only available for minions in the <em>online</em> state.
            </div>
          )}

          {data.status === 'online' && (
            <GrainsTable grains={data.grains ?? {}} search={grainSearch} onSearchChange={setGrainSearch} />
          )}
        </>
      )}
    </div>
  )
}

function NotFoundPanel({ minionId }: { minionId: string }) {
  return (
    <div className="flex flex-col gap-4">
      <Link to="/minions" className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:underline">
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to minions
      </Link>
      <div className="rounded-md border p-6 text-sm">
        <p className="font-medium">Minion not found</p>
        <p className="text-muted-foreground">
          No minion named <span className="font-mono">{minionId}</span> is known to the master in
          any state.
        </p>
      </div>
    </div>
  )
}

function GrainsTable({
  grains,
  search,
  onSearchChange,
}: {
  grains: Record<string, unknown>
  search: string
  onSearchChange: (v: string) => void
}) {
  const rows = useMemo(() => {
    const entries = Object.entries(grains).sort(([a], [b]) => a.localeCompare(b))
    const needle = search.trim().toLowerCase()
    if (!needle) return entries
    return entries.filter(([k]) => k.toLowerCase().includes(needle))
  }, [grains, search])

  return (
    <div className="flex flex-col gap-2">
      <div className="space-y-1">
        <Label htmlFor="grain-search" className="text-xs">Filter grains by key</Label>
        <Input
          id="grain-search"
          placeholder="os, ip, kernel…"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          autoComplete="off"
        />
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-1/3">Key</TableHead>
              <TableHead>Value</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={2} className="h-16 text-center text-muted-foreground">
                  {search ? 'No grains match the filter.' : 'No grains reported.'}
                </TableCell>
              </TableRow>
            )}
            {rows.map(([key, value]) => (
              <TableRow key={key}>
                <TableCell className="font-mono text-xs">{key}</TableCell>
                <TableCell className="font-mono text-xs">{formatValue(value)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

import { useState } from 'react'

import { MinionRunPanel } from '@/features/fleet/minion-run-panel'

import { cn } from '@/lib/utils'

import type { components } from '@/shared/api/types.gen'

import { useMinionRuns } from './use-minion-runs'

type RunSummary = components['schemas']['MinionRunSummary']
type FleetMinionShape = components['schemas']['MinionHealthOut']


const STATUS_TINT: Record<RunSummary['status'], string> = {
  blocked: 'text-muted-foreground',
  changed: 'text-warning',
  healthy: 'text-success',
  unhealthy: 'text-destructive',
}

// RunSummary['status'] is a strict subset of MinionHealthOut['status']
// (the fleet enum also has 'stale' and 'unknown'), so identity-map.
const STATUS_TO_FLEET: Record<RunSummary['status'], FleetMinionShape['status']> = {
  blocked: 'blocked',
  changed: 'changed',
  healthy: 'healthy',
  unhealthy: 'unhealthy',
}


export function MinionRunsTable({ minionId }: { minionId: string }) {
  const { data, isError, isLoading } = useMinionRuns(minionId, 20)
  const [selected, setSelected] = useState<RunSummary | null>(null)
  const [panelOpen, setPanelOpen] = useState(false)

  // P23's MinionRunPanel expects a fleet MinionHealthOut shape. Shim it.
  const fleetShim: FleetMinionShape | null = selected
    ? {
      change_count: selected.change_count,
      completed_at: selected.completed_at,
      duration_ms: selected.duration_ms,
      fail_count: selected.fail_count,
      jid: selected.jid,
      minion_id: minionId,
      online: true,
      pass_count: selected.pass_count,
      run_id: selected.id,
      status: STATUS_TO_FLEET[selected.status],
      total_count: selected.total_count,
    }
    : null

  return (
    <section className="rounded-lg border border-border bg-card">
      <header className="border-b border-border px-4 py-2">
        <h2 className="text-sm font-semibold">Recent highstate runs</h2>
        <p className="text-xs text-muted-foreground">
          Last {data?.total ?? 0} runs · click a row for details
        </p>
      </header>
      {isLoading && (
        <p className="px-4 py-3 text-sm text-muted-foreground">Loading…</p>
      )}
      {isError && (
        <p className="px-4 py-3 text-sm text-destructive">Failed to load runs.</p>
      )}
      {data && data.runs.length === 0 && (
        <p className="px-4 py-3 text-sm text-muted-foreground">
          No highstate runs ingested for this minion yet. Enable the fleet poller in Settings → Pollers.
        </p>
      )}
      {data && data.runs.length > 0 && (
        <table className="w-full text-sm">
          <thead className="border-b border-border text-left text-xs text-muted-foreground">
            <tr>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">When</th>
              <th className="px-4 py-2 font-medium">Fun</th>
              <th className="px-4 py-2 font-medium text-right">Pass / Changed / Failed</th>
              <th className="px-4 py-2 font-medium text-right">Duration</th>
            </tr>
          </thead>
          <tbody>
            {data.runs.map((r) => (
              <tr
                key={r.id}
                onClick={() => {
                  setSelected(r)
                  setPanelOpen(true)
                }}
                className="cursor-pointer border-b border-border last:border-0 hover:bg-muted/50"
              >
                <td className={cn('px-4 py-2 capitalize', STATUS_TINT[r.status])}>{r.status}</td>
                <td className="px-4 py-2 text-muted-foreground">
                  {new Date(r.completed_at).toLocaleString()}
                </td>
                <td className="px-4 py-2 font-mono text-xs">{r.fun}</td>
                <td className="px-4 py-2 text-right">
                  <span className="text-success">{r.pass_count}</span>
                  {' · '}
                  <span className="text-warning">{r.change_count}</span>
                  {' · '}
                  <span className="text-destructive">{r.fail_count}</span>
                </td>
                <td className="px-4 py-2 text-right text-muted-foreground">
                  {(r.duration_ms / 1000).toFixed(2)}s
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {fleetShim && (
        <MinionRunPanel
          minion={fleetShim}
          open={panelOpen}
          onOpenChange={setPanelOpen}
        />
      )}
    </section>
  )
}

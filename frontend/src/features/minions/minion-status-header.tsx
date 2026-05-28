import { Cpu, Server, Wifi, WifiOff } from 'lucide-react'

import { cn } from '@/lib/utils'

import type { components } from '@/shared/api/types.gen'
type Minion = components['schemas']['MinionDetail']

const STATUS_STYLE: Record<string, string> = {
  denied: 'border-border bg-muted text-muted-foreground',
  offline: 'border-destructive/40 bg-destructive/15 text-destructive',
  online: 'border-success/40 bg-success/15 text-success',
  pending: 'border-warning/40 bg-warning/15 text-warning',
  rejected: 'border-border bg-muted text-muted-foreground',
}


export function MinionStatusHeader({ minion }: { minion: Minion }) {
  const g = (minion.grains ?? {}) as Record<string, unknown>
  const os = `${asStr(g.os) ?? '—'} ${asStr(g.osrelease) ?? ''}`.trim()
  const kernel = `${asStr(g.kernel) ?? '—'} ${asStr(g.kernelrelease) ?? ''}`.trim()
  const numCpus = asNum(g.num_cpus)
  const memMb = asNum(g.mem_total)
  const memGib = memMb !== null ? (memMb / 1024).toFixed(1) : null

  return (
    <header className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="font-mono text-2xl font-semibold tracking-tight">{minion.id}</h1>
        <span
          className={cn(
            'inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs',
            STATUS_STYLE[minion.status] ?? STATUS_STYLE.denied,
          )}
        >
          {minion.status === 'online' ? <Wifi className="size-3" /> : <WifiOff className="size-3" />}
          {minion.status}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
        <KeyFact label="IP" value={minion.ip ?? '—'} mono />
        <KeyFact label="OS" value={os || '—'} icon={Server} />
        <KeyFact label="Kernel" value={kernel || '—'} />
        <KeyFact
          label="Hardware"
          value={numCpus !== null && memGib !== null ? `${numCpus} cores · ${memGib} GiB` : '—'}
          icon={Cpu}
        />
      </div>
    </header>
  )
}


function KeyFact({
  label,
  value,
  icon: Icon,
  mono,
}: {
  label: string
  value: string
  icon?: React.ComponentType<{ className?: string }>
  mono?: boolean
}) {
  return (
    <div>
      <p className="flex items-center gap-1 text-xs text-muted-foreground">
        {Icon && <Icon className="size-3" />}
        {label}
      </p>
      <p className={cn('mt-0.5 truncate', mono && 'font-mono text-sm')}>{value}</p>
    </div>
  )
}


function asStr(v: unknown): string | null {
  if (typeof v === 'string' && v) return v
  return null
}
function asNum(v: unknown): number | null {
  if (typeof v === 'number' && Number.isFinite(v)) return v
  return null
}

import { Search } from 'lucide-react'
import { useMemo, useState } from 'react'

import { Input } from '@/components/ui/input'


export function MinionGrainExplorer({ grains }: { grains: Record<string, unknown> | null }) {
  const [filter, setFilter] = useState('')

  const flat = useMemo(() => _flatten(grains ?? {}), [grains])
  const filtered = useMemo(() => {
    if (!filter.trim()) return flat
    const q = filter.trim().toLowerCase()
    return flat.filter(([k, v]) => k.toLowerCase().includes(q) || v.toLowerCase().includes(q))
  }, [flat, filter])

  if (grains === null) {
    return (
      <section className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">
          No grains available yet. Enable the grains poller in Settings → Pollers.
        </p>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-border bg-card">
      <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-2">
        <div>
          <h2 className="text-sm font-semibold">Grains</h2>
          <p className="text-xs text-muted-foreground">
            {flat.length} keys
            {filtered.length !== flat.length && ` · showing ${filtered.length}`}
          </p>
        </div>
        <div className="relative w-64">
          <Search className="absolute left-2 top-1/2 size-3 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label="Filter grains"
            className="h-8 pl-7"
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter…"
            value={filter}
          />
        </div>
      </header>
      <div className="max-h-[480px] overflow-y-auto">
        <table className="w-full text-xs">
          <tbody>
            {filtered.map(([k, v]) => (
              <tr key={k} className="border-b border-border last:border-0">
                <td className="w-1/3 truncate px-4 py-1.5 align-top font-mono text-muted-foreground">{k}</td>
                <td className="break-all px-4 py-1.5 font-mono">{v}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={2} className="px-4 py-6 text-center text-muted-foreground">
                  No grains match the filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}


function _flatten(value: unknown, prefix = ''): [string, string][] {
  if (value === null || value === undefined) {
    return [[prefix || '(root)', String(value)]]
  }
  if (typeof value !== 'object') {
    return [[prefix || '(root)', String(value)]]
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return [[prefix || '(root)', '[]']]
    if (value.every((x) => typeof x !== 'object' || x === null)) {
      return [[prefix || '(root)', value.map(String).join(', ')]]
    }
    return value.flatMap((v, i) => _flatten(v, prefix ? `${prefix}[${i}]` : `[${i}]`))
  }
  return Object.entries(value as Record<string, unknown>).flatMap(([k, v]) =>
    _flatten(v, prefix ? `${prefix}.${k}` : k),
  )
}

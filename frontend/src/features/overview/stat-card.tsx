import type { LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

type Tone = 'amber' | 'success' | 'destructive' | 'muted'

const toneStyles: Record<Tone, { wrap: string; icon: string }> = {
  amber: {
    wrap: 'bg-primary/10 ring-primary/25 text-primary',
    icon: 'text-primary',
  },
  success: {
    wrap: 'bg-success/10 ring-success/25 text-success',
    icon: 'text-success',
  },
  destructive: {
    wrap: 'bg-destructive/10 ring-destructive/30 text-destructive',
    icon: 'text-destructive',
  },
  muted: {
    wrap: 'bg-muted ring-border text-muted-foreground',
    icon: 'text-muted-foreground',
  },
}

interface StatCardProps {
  label: string
  value: string | number
  hint?: string
  icon: LucideIcon
  tone?: Tone
  loading?: boolean
}

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = 'amber',
  loading,
}: StatCardProps) {
  const tones = toneStyles[tone]
  return (
    <div className="group relative overflow-hidden rounded-lg border border-border/80 bg-card p-4 transition-colors hover:border-primary/40">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-[11px] font-medium uppercase tracking-[0.15em] text-muted-foreground">
            {label}
          </span>
          {loading ? (
            <span
              aria-hidden
              className="mt-0.5 h-7 w-16 animate-pulse rounded bg-muted"
            />
          ) : (
            <span className="text-2xl font-semibold tracking-tight tabular-nums">
              {value}
            </span>
          )}
          {hint && (
            <span className="text-xs text-muted-foreground">{hint}</span>
          )}
        </div>
        <span
          aria-hidden
          className={cn(
            'flex h-9 w-9 shrink-0 items-center justify-center rounded-md ring-1',
            tones.wrap,
          )}
        >
          <Icon className={cn('h-4 w-4', tones.icon)} />
        </span>
      </div>
    </div>
  )
}

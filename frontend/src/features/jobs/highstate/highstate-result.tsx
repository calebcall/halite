// frontend/src/features/jobs/highstate/highstate-result.tsx
import { Check, ChevronDown, Minus, X } from 'lucide-react'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { hasChanges, type ParsedState, summarize } from './parse'

export function HighstateResult({
  states,
  filterFailures = false,
}: {
  states: ParsedState[]
  filterFailures?: boolean
}) {
  const stats = summarize(states)
  const visibleStates = filterFailures
    ? states.filter((s) => s.result === false)
    : states
  return (
    <div className="flex flex-col gap-2 p-3">
      <HighstateSummary stats={stats} />
      {filterFailures && visibleStates.length === 0 && (
        <p className="text-xs text-muted-foreground italic px-1">No failed states.</p>
      )}
      <div className="flex flex-col gap-1">
        {visibleStates.map((s) => (
          <HighstateRow key={`${s.runNum}-${s.module}-${s.stateId}-${s.fun}`} state={s} />
        ))}
      </div>
    </div>
  )
}

function HighstateSummary({ stats }: { stats: ReturnType<typeof summarize> }) {
  const seconds = (stats.totalDurationMs / 1000).toFixed(2)
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md bg-muted/40 px-3 py-2 text-xs">
      <span><span className="font-semibold">{stats.total}</span> state{stats.total === 1 ? '' : 's'}</span>
      <span className="text-muted-foreground">·</span>
      <span><span className="font-semibold">{stats.withChanges}</span> with changes</span>
      <span className="text-muted-foreground">·</span>
      <span className={stats.failed > 0 ? 'text-destructive' : undefined}>
        <span className="font-semibold">{stats.failed}</span> failed
      </span>
      <span className="text-muted-foreground">·</span>
      <span><span className="font-semibold">{seconds}s</span> total</span>
    </div>
  )
}

function HighstateRow({ state }: { state: ParsedState }) {
  const [expanded, setExpanded] = useState(false)
  const tone = rowTone(state)
  const ms = state.duration !== null ? `${state.duration.toFixed(0)}ms` : null
  const hasChangesBlock = hasChanges(state)
  const panelId = `state-${state.runNum}-${state.module}-${state.stateId}`

  return (
    <div className={`rounded-md border-l-4 ${tone.border} bg-card`}>
      <Button
        type="button"
        variant="ghost"
        className="flex h-auto w-full items-start justify-between gap-3 rounded-none px-3 py-2 text-left"
        aria-expanded={expanded}
        aria-controls={hasChangesBlock ? panelId : undefined}
        onClick={() => hasChangesBlock && setExpanded((v) => !v)}
      >
        <div className="flex flex-col items-start gap-1 min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {tone.icon}
            <Badge variant="outline" className="font-mono text-[10px]">
              {state.module}.{state.fun}
            </Badge>
            <span className="font-mono text-xs">{state.stateId}</span>
            {state.name && state.name !== state.stateId && (
              <span className="text-muted-foreground">({state.name})</span>
            )}
            {ms && <span className="text-muted-foreground">{ms}</span>}
            {hasChangesBlock && (
              <Badge className="bg-blue-100 text-blue-900 text-[10px] hover:bg-blue-100 dark:bg-blue-950/40 dark:text-blue-200">
                changes
              </Badge>
            )}
          </div>
          {state.comment && (
            <p className="text-xs text-muted-foreground whitespace-pre-wrap break-words">
              {state.comment}
            </p>
          )}
        </div>
        {hasChangesBlock && (
          <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform shrink-0 mt-1 ${expanded ? 'rotate-180' : ''}`} />
        )}
      </Button>
      <pre
        id={hasChangesBlock ? panelId : undefined}
        hidden={!hasChangesBlock || !expanded}
        className="overflow-x-auto border-t bg-muted/20 p-3 text-xs"
      >
        {hasChangesBlock ? JSON.stringify(state.changes, null, 2) : ''}
      </pre>
    </div>
  )
}

function rowTone(state: ParsedState): { border: string; icon: React.ReactNode } {
  if (state.result === false) {
    return {
      border: 'border-destructive',
      icon: <X className="h-3.5 w-3.5 text-destructive" />,
    }
  }
  if (state.result === null) {
    return {
      border: 'border-muted-foreground/40',
      icon: <Minus className="h-3.5 w-3.5 text-muted-foreground" />,
    }
  }
  if (hasChanges(state)) {
    return {
      border: 'border-primary/60',
      icon: <Check className="h-3.5 w-3.5 text-primary" />,
    }
  }
  return {
    border: 'border-success/60',
    icon: <Check className="h-3.5 w-3.5 text-success" />,
  }
}

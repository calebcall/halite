// frontend/src/features/jobs/highstate/highstate-by-state-view.tsx
import { Check, ChevronDown, Minus, X } from 'lucide-react'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { StateGroup, StateOutcome } from './group-by-state'
import { hasChanges, type ParsedState } from './parse'

export function HighstateByStateView({
  groups,
  failuresOnly = false,
}: {
  groups: StateGroup[]
  failuresOnly?: boolean
}) {
  const visible = failuresOnly ? groups.filter((g) => g.failed > 0) : groups
  if (visible.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">
        {failuresOnly ? 'No failed states.' : 'No highstate output to group.'}
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-2">
      {visible.map((g) => (
        <StateGroupRow
          key={`${g.module}|${g.stateId}|${g.fun}`}
          group={g}
          failuresOnly={failuresOnly}
        />
      ))}
    </div>
  )
}

function StateGroupRow({
  group,
  failuresOnly,
}: {
  group: StateGroup
  failuresOnly: boolean
}) {
  // Auto-expand groups with failures so the operator doesn't have to click.
  const [open, setOpen] = useState(group.failed > 0)
  const total = group.outcomes.length
  const tone = groupTone(group)
  const panelId = `state-group-${group.module}-${group.stateId}`

  const visibleOutcomes = failuresOnly
    ? group.outcomes.filter((o) => o.state.result === false)
    : group.outcomes

  return (
    <div className={`rounded-md border-l-4 ${tone.border} bg-card`}>
      <Button
        type="button"
        variant="ghost"
        className="flex h-auto w-full items-start justify-between gap-3 rounded-none px-3 py-2 text-left"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
      >
        <div className="flex flex-col items-start gap-1 min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge variant="outline" className="font-mono text-[10px]">
              {group.module}.{group.fun}
            </Badge>
            <span className="font-mono text-xs">{group.stateId}</span>
            <span className="text-muted-foreground">
              on {total} minion{total === 1 ? '' : 's'}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
            {group.passed > 0 && (
              <span>
                <span className="font-semibold text-success">{group.passed}</span> passed
              </span>
            )}
            {group.withChanges > 0 && (
              <span>
                <span className="font-semibold text-primary">{group.withChanges}</span> with changes
              </span>
            )}
            {group.failed > 0 && (
              <span>
                <span className="font-semibold text-destructive">{group.failed}</span> failed
              </span>
            )}
            {group.testMode > 0 && (
              <span>
                <span className="font-semibold">{group.testMode}</span> test-mode
              </span>
            )}
          </div>
        </div>
        <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform shrink-0 mt-1 ${open ? 'rotate-180' : ''}`} />
      </Button>
      <div
        id={panelId}
        hidden={!open}
        className="border-t bg-muted/20 px-3 py-2 flex flex-col gap-1"
      >
        {visibleOutcomes.length === 0 && (
          <p className="text-xs text-muted-foreground italic">No failed outcomes in this group.</p>
        )}
        {visibleOutcomes.map((o) => (
          <OutcomeRow key={o.minion} outcome={o} />
        ))}
      </div>
    </div>
  )
}

function OutcomeRow({ outcome }: { outcome: StateOutcome }) {
  const { state } = outcome
  const ms = state.duration !== null ? `${state.duration.toFixed(0)}ms` : null
  const icon = outcomeIcon(state)
  return (
    <div className="flex items-start gap-2 text-xs">
      {icon}
      <span className="font-mono shrink-0">{outcome.minion}</span>
      {ms && <span className="text-muted-foreground shrink-0">{ms}</span>}
      {hasChanges(state) && (
        <Badge variant="outline" className="text-[10px] shrink-0">changes</Badge>
      )}
      {state.comment && (
        <span className="text-muted-foreground whitespace-pre-wrap break-words min-w-0">
          {state.comment}
        </span>
      )}
    </div>
  )
}

function outcomeIcon(state: ParsedState) {
  if (state.result === false) {
    return <X className="h-3.5 w-3.5 text-destructive shrink-0 mt-0.5" />
  }
  if (state.result === null) {
    return <Minus className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />
  }
  return <Check className="h-3.5 w-3.5 text-success shrink-0 mt-0.5" />
}

function groupTone(g: StateGroup): { border: string } {
  if (g.failed > 0) return { border: 'border-destructive' }
  if (g.withChanges > 0) return { border: 'border-primary/60' }
  if (g.testMode > 0 && g.passed === 0) return { border: 'border-muted-foreground/40' }
  return { border: 'border-success/60' }
}

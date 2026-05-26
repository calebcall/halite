// frontend/src/features/jobs/highstate/group-by-state.ts
import { isBlockedReturn, type MinionResultLite } from './job-summary'
import { hasChanges, parseHighstate, type ParsedState } from './parse'

export interface StateOutcome {
  minion: string
  state: ParsedState
}

export interface StateGroup {
  // Identity — every outcome in this group shares this triple
  module: string
  stateId: string
  fun: string
  // First-seen name (names may vary across minions when templated by grain)
  sampleName: string
  // Per-minion outcomes (sorted: failed first, then with-changes, then alpha)
  outcomes: StateOutcome[]
  // Aggregate counts
  passed: number       // result === true AND no changes
  withChanges: number  // result === true AND non-empty changes
  failed: number       // result === false
  testMode: number     // result === null
}

function groupKey(s: ParsedState): string {
  return `${s.module}|${s.stateId}|${s.fun}`
}

function compareGroups(a: StateGroup, b: StateGroup): number {
  if (a.failed > 0 && b.failed === 0) return -1
  if (a.failed === 0 && b.failed > 0) return 1
  if (a.withChanges > 0 && b.withChanges === 0) return -1
  if (a.withChanges === 0 && b.withChanges > 0) return 1
  return a.stateId.localeCompare(b.stateId)
}

function compareOutcomes(a: StateOutcome, b: StateOutcome): number {
  if (a.state.result === false && b.state.result !== false) return -1
  if (a.state.result !== false && b.state.result === false) return 1
  const aChanged = hasChanges(a.state)
  const bChanged = hasChanges(b.state)
  if (aChanged && !bChanged) return -1
  if (!aChanged && bChanged) return 1
  return a.minion.localeCompare(b.minion)
}

/**
 * Pivot per-minion highstate results into per-state groups.
 *
 * Skips minions whose return_value isn't highstate-shaped (`parseHighstate`
 * returns null) — those would muddy the by-state view. Also skips blocked
 * minions (Plan 17's "function already running" busy responses).
 *
 * Returns groups sorted failed-first → with-changes → alpha by stateId.
 * Within each group, outcomes are sorted the same way by minion.
 */
export function groupByState(results: MinionResultLite[]): StateGroup[] {
  const groups = new Map<string, StateGroup>()

  for (const r of results) {
    if (isBlockedReturn(r.return_value)) continue
    const parsed = parseHighstate(r.return_value)
    if (!parsed) continue

    for (const state of parsed) {
      const key = groupKey(state)
      let g = groups.get(key)
      if (!g) {
        g = {
          failed: 0,
          fun: state.fun,
          module: state.module,
          outcomes: [],
          passed: 0,
          sampleName: state.name,
          stateId: state.stateId,
          testMode: 0,
          withChanges: 0,
        }
        groups.set(key, g)
      }
      g.outcomes.push({ minion: r.minion, state })
      if (state.result === false) {
        g.failed++
      } else if (state.result === null) {
        g.testMode++
      } else if (hasChanges(state)) {
        g.withChanges++
      } else {
        g.passed++
      }
    }
  }

  const out = Array.from(groups.values())
  for (const g of out) {
    g.outcomes.sort(compareOutcomes)
  }
  out.sort(compareGroups)
  return out
}

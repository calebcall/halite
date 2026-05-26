// frontend/src/features/jobs/highstate/job-summary.ts
import { parseHighstate } from './parse'

// Minimal shape we need from each minion result. Decoupling from the
// generated JobMinionResult type lets the unit test feed plain objects.
export interface MinionResultLite {
  minion: string
  success?: boolean | null | undefined
  return_value?: unknown
}

export interface JobHighstateAggregate {
  // Minion-level counts
  totalMinions: number
  minionsAllSuccess: number   // produced highstate output AND every state succeeded
  minionsWithFailures: number // produced highstate output AND at least one state failed
  minionsBlocked: number      // returned salt's "function already running" message
  minionsNonHighstate: number // produced output but NOT highstate-shaped (and not blocked)
  // State-level counts (summed across all minions)
  totalStateFailures: number
  totalStatesWithChanges: number
}

// Matches salt's per-minion "function already running" busy response.
// Format example:
//   The function "state.apply" is running as PID 544532 and was started at
//   2026, May 26 16:10:22.541673 with jid 20260526161022541673
// salt-api typically wraps the string in a one-element list.
const BLOCKED_RE = /The function ".+" is running as PID/

export function isBlockedReturn(value: unknown): boolean {
  if (typeof value === 'string') return BLOCKED_RE.test(value)
  if (Array.isArray(value)) {
    return value.some((v) => typeof v === 'string' && BLOCKED_RE.test(v))
  }
  return false
}

/**
 * Aggregate highstate stats across every minion of a job.
 *
 * Returns null when NO minion produced highstate-shaped output — that's
 * the signal to skip the job-level summary and failures-only filter
 * entirely (the job is a regular cmd.run / test.ping / etc., not a
 * state.apply).
 */
export function summarizeJobHighstate(
  results: MinionResultLite[],
): JobHighstateAggregate | null {
  let totalMinions = 0
  let minionsAllSuccess = 0
  let minionsWithFailures = 0
  let minionsBlocked = 0
  let minionsNonHighstate = 0
  let totalStateFailures = 0
  let totalStatesWithChanges = 0
  let anyHighstate = false

  for (const r of results) {
    totalMinions++
    // Check blocked BEFORE parseHighstate — blocked returns are
    // list/string-shaped and parseHighstate would otherwise lump them
    // into the generic non-highstate bucket.
    if (isBlockedReturn(r.return_value)) {
      minionsBlocked++
      continue
    }
    const parsed = parseHighstate(r.return_value)
    if (!parsed) {
      minionsNonHighstate++
      continue
    }
    anyHighstate = true
    let failed = 0
    let withChanges = 0
    for (const s of parsed) {
      if (s.result === false) failed++
      if (hasNonEmptyChanges(s.changes)) withChanges++
    }
    totalStateFailures += failed
    totalStatesWithChanges += withChanges
    if (failed > 0) {
      minionsWithFailures++
    } else {
      minionsAllSuccess++
    }
  }

  if (!anyHighstate) return null
  return {
    totalMinions,
    minionsAllSuccess,
    minionsWithFailures,
    minionsBlocked,
    minionsNonHighstate,
    totalStateFailures,
    totalStatesWithChanges,
  }
}

function hasNonEmptyChanges(c: unknown): boolean {
  if (!c) return false
  if (typeof c !== 'object') return false
  if (Array.isArray(c)) return c.length > 0
  return Object.keys(c as Record<string, unknown>).length > 0
}

/**
 * Predicate: should this minion's card be visible when failures-only
 * mode is on? Visible when:
 *   - The minion's top-level success is false (a connect/dispatch error), OR
 *   - The minion produced highstate output with at least one failed state.
 *
 * Non-highstate minions with success !== false are hidden because there
 * is no per-state failure granularity to investigate.
 */
export function minionHasFailures(r: MinionResultLite): boolean {
  if (r.success === false) return true
  const parsed = parseHighstate(r.return_value)
  if (!parsed) return false
  return parsed.some((s) => s.result === false)
}

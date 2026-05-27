// frontend/src/features/jobs/highstate/parse.ts

// Salt's low-state result keys: "module_|-state_id_|-name_|-fun".
// State IDs and names can contain anything (including underscores,
// newlines, and the substring `_|`), so we anchor with `^` and `$`
// and use the unique `_|-` separator (underscore-pipe-dash) which
// doesn't legally appear inside any of the four positions. The `s`
// (dotall) flag is required because cmd.run state names commonly
// contain multi-line shell scripts with literal newline characters.
// Module + fun segments allow digits (e.g. `x509`, `keystone_v3`) — salt
// has perfectly normal modules with digits in the name. Restricting to
// [a-z_]+ would (and did) make the master's TLS-cert states show as
// "unknown JSON" in the UI.
const LOWSTATE_KEY = /^([a-z0-9_]+)_\|-(.*?)_\|-(.*?)_\|-([a-z0-9_]+)$/s

export type ParsedState = {
  module: string
  stateId: string
  name: string
  fun: string
  result: boolean | null  // null => test mode / no-op
  comment: string
  changes: unknown  // intentionally unknown — shape varies per state module
  duration: number | null  // milliseconds
  runNum: number
  sls: string | null
  startTime: string | null
}

export function parseHighstate(value: unknown): ParsedState[] | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }
  const entries = Object.entries(value as Record<string, unknown>)
  if (entries.length === 0) {
    return null
  }
  const parsed: ParsedState[] = []
  for (const [key, raw] of entries) {
    const m = LOWSTATE_KEY.exec(key)
    if (!m) return null
    if (!raw || typeof raw !== 'object') return null
    const v = raw as Record<string, unknown>
    if (!('result' in v) || !('comment' in v)) return null

    parsed.push({
      module: m[1],
      stateId: m[2],
      name: m[3],
      fun: m[4],
      result: v.result === true ? true : v.result === false ? false : null,
      comment: typeof v.comment === 'string' ? v.comment : String(v.comment ?? ''),
      changes: v.changes,
      duration: typeof v.duration === 'number' ? v.duration : null,
      runNum: typeof v.__run_num__ === 'number' ? v.__run_num__ : 0,
      sls: typeof v.__sls__ === 'string' ? v.__sls__ : null,
      startTime: typeof v.start_time === 'string' ? v.start_time : null,
    })
  }
  parsed.sort((a, b) => a.runNum - b.runNum)
  return parsed
}

export function hasChanges(state: ParsedState): boolean {
  if (!state.changes) return false
  if (typeof state.changes !== 'object') return false
  if (Array.isArray(state.changes)) return state.changes.length > 0
  return Object.keys(state.changes as Record<string, unknown>).length > 0
}

export type HighstateSummaryStats = {
  total: number
  withChanges: number
  failed: number
  totalDurationMs: number
}

export function summarize(states: ParsedState[]): HighstateSummaryStats {
  let withChanges = 0
  let failed = 0
  let totalDurationMs = 0
  for (const s of states) {
    if (hasChanges(s)) withChanges++
    if (s.result === false) failed++
    if (s.duration !== null) totalDurationMs += s.duration
  }
  return { total: states.length, withChanges, failed, totalDurationMs }
}

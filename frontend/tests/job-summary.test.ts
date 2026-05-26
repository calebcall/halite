// frontend/tests/job-summary.test.ts
import { describe, expect, it } from 'vitest'

import {
  isBlockedReturn,
  type MinionResultLite,
  minionHasFailures,
  summarizeJobHighstate,
} from '@/features/jobs/highstate/job-summary'

const blockedString =
  'The function "state.apply" is running as PID 544532 and was started at 2026, May 26 16:10:22.541673 with jid 20260526161022541673'
const blockedListReturn = [blockedString]

const stateOk = (id: string) => ({
  [`pkg_|-${id}_|-x_|-installed`]: {
    name: 'x',
    result: true,
    comment: '',
    changes: {},
    __run_num__: 0,
  },
})

const stateOkWithChanges = (id: string) => ({
  [`pkg_|-${id}_|-x_|-installed`]: {
    name: 'x',
    result: true,
    comment: '',
    changes: { x: { new: '1.0' } },
    __run_num__: 0,
  },
})

const stateFailed = (id: string) => ({
  [`pkg_|-${id}_|-x_|-installed`]: {
    name: 'x',
    result: false,
    comment: 'broken',
    changes: {},
    __run_num__: 0,
  },
})

const minion = (
  name: string,
  return_value: unknown,
  success: boolean | null = true,
): MinionResultLite => ({ minion: name, success, return_value })

describe('summarizeJobHighstate', () => {
  it('returns null for empty results', () => {
    expect(summarizeJobHighstate([])).toBeNull()
  })

  it('returns null when no minion has highstate-shaped output', () => {
    expect(
      summarizeJobHighstate([
        minion('a', true),
        minion('b', 'hello'),
        minion('c', { 'web-01': 'ok' }),
      ]),
    ).toBeNull()
  })

  it('aggregates an all-success highstate run', () => {
    const out = summarizeJobHighstate([
      minion('a', stateOk('one')),
      minion('b', stateOkWithChanges('two')),
    ])
    expect(out).toEqual({
      totalMinions: 2,
      minionsAllSuccess: 2,
      minionsWithFailures: 0,
      minionsBlocked: 0,
      minionsNonHighstate: 0,
      totalStateFailures: 0,
      totalStatesWithChanges: 1,
    })
  })

  it('aggregates a mixed-success run', () => {
    const out = summarizeJobHighstate([
      minion('a', stateOk('one')),
      minion('b', stateFailed('two')),
      minion('c', { ...stateOk('three'), ...stateFailed('four') }),
    ])
    expect(out).toEqual({
      totalMinions: 3,
      minionsAllSuccess: 1,
      minionsWithFailures: 2,
      minionsBlocked: 0,
      minionsNonHighstate: 0,
      totalStateFailures: 2,
      totalStatesWithChanges: 0,
    })
  })

  it('counts non-highstate minions but still reports counts', () => {
    const out = summarizeJobHighstate([
      minion('a', stateOk('one')),
      minion('b', 'cmd output'),
      minion('c', true),
    ])
    expect(out).toEqual({
      totalMinions: 3,
      minionsAllSuccess: 1,
      minionsWithFailures: 0,
      minionsBlocked: 0,
      minionsNonHighstate: 2,
      totalStateFailures: 0,
      totalStatesWithChanges: 0,
    })
  })

  it('counts withChanges only for non-empty changes', () => {
    const out = summarizeJobHighstate([
      minion('a', stateOk('a')),
      minion('b', stateOkWithChanges('b')),
      minion('c', stateOkWithChanges('c')),
    ])
    expect(out?.totalStatesWithChanges).toBe(2)
  })

  it('counts blocked minions separately from non-highstate output', () => {
    const out = summarizeJobHighstate([
      minion('a', stateOk('one')),
      minion('b', blockedListReturn, false),
      minion('c', blockedListReturn, false),
      minion('d', 'plain string', false),
    ])
    expect(out).toEqual({
      totalMinions: 4,
      minionsAllSuccess: 1,
      minionsWithFailures: 0,
      minionsBlocked: 2,
      minionsNonHighstate: 1,
      totalStateFailures: 0,
      totalStatesWithChanges: 0,
    })
  })
})

describe('isBlockedReturn', () => {
  it('detects the salt-busy message inside a one-element list', () => {
    expect(isBlockedReturn(blockedListReturn)).toBe(true)
  })

  it('detects the salt-busy message as a plain string', () => {
    expect(isBlockedReturn(blockedString)).toBe(true)
  })

  it('false for arbitrary strings', () => {
    expect(isBlockedReturn('something failed')).toBe(false)
    expect(isBlockedReturn(['a', 'b'])).toBe(false)
  })

  it('false for dicts and other shapes', () => {
    expect(isBlockedReturn({ result: false })).toBe(false)
    expect(isBlockedReturn(null)).toBe(false)
    expect(isBlockedReturn(undefined)).toBe(false)
    expect(isBlockedReturn(42)).toBe(false)
  })
})

describe('minionHasFailures', () => {
  it('true when top-level success is false', () => {
    expect(minionHasFailures(minion('a', 'error', false))).toBe(true)
  })

  it('true when highstate has at least one failed state', () => {
    expect(minionHasFailures(minion('a', stateFailed('x')))).toBe(true)
  })

  it('false when highstate has no failed states', () => {
    expect(minionHasFailures(minion('a', stateOk('x')))).toBe(false)
  })

  it('false for non-highstate output with success true', () => {
    expect(minionHasFailures(minion('a', 'cmd output'))).toBe(false)
  })

  it('false for non-highstate output with success null', () => {
    expect(minionHasFailures(minion('a', 'cmd output', null))).toBe(false)
  })
})

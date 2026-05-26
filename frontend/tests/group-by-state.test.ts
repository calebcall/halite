// frontend/tests/group-by-state.test.ts
import { describe, expect, it } from 'vitest'

import { groupByState } from '@/features/jobs/highstate/group-by-state'
import type { MinionResultLite } from '@/features/jobs/highstate/job-summary'

const ok = (id: string) => ({
  [`pkg_|-${id}_|-x_|-installed`]: {
    name: 'x', result: true, comment: '', changes: {}, __run_num__: 0,
  },
})

const okChanged = (id: string) => ({
  [`pkg_|-${id}_|-x_|-installed`]: {
    name: 'x', result: true, comment: '', changes: { x: { new: '1.0' } }, __run_num__: 0,
  },
})

const failed = (id: string) => ({
  [`pkg_|-${id}_|-x_|-installed`]: {
    name: 'x', result: false, comment: 'broken', changes: {}, __run_num__: 0,
  },
})

const testMode = (id: string) => ({
  [`pkg_|-${id}_|-x_|-installed`]: {
    name: 'x', result: null, comment: 'would install', changes: {}, __run_num__: 0,
  },
})

const minion = (
  name: string,
  return_value: unknown,
  success: boolean | null = true,
): MinionResultLite => ({ minion: name, success, return_value })

describe('groupByState', () => {
  it('returns empty for no results', () => {
    expect(groupByState([])).toEqual([])
  })

  it('returns empty when no minion has highstate output', () => {
    expect(groupByState([
      minion('a', 'string return'),
      minion('b', { foo: 'bar' }),
    ])).toEqual([])
  })

  it('groups a single state across multiple minions', () => {
    const groups = groupByState([
      minion('web-01', ok('install_nginx')),
      minion('web-02', ok('install_nginx')),
      minion('web-03', okChanged('install_nginx')),
    ])
    expect(groups).toHaveLength(1)
    const g = groups[0]
    expect(g.stateId).toBe('install_nginx')
    expect(g.module).toBe('pkg')
    expect(g.fun).toBe('installed')
    expect(g.outcomes).toHaveLength(3)
    expect(g.passed).toBe(2)
    expect(g.withChanges).toBe(1)
    expect(g.failed).toBe(0)
  })

  it('produces separate groups for different state IDs', () => {
    const groups = groupByState([
      minion('a', { ...ok('a'), ...ok('b') }),
      minion('b', ok('a')),
    ])
    expect(groups.map((g) => g.stateId).sort()).toEqual(['a', 'b'])
  })

  it('counts failures separately and sorts failed groups first', () => {
    const groups = groupByState([
      minion('a', { ...ok('clean'), ...failed('broken') }),
      minion('b', { ...ok('clean'), ...ok('broken') }),
    ])
    // 'broken' has 1 failure → sorted first
    expect(groups.map((g) => g.stateId)).toEqual(['broken', 'clean'])
    expect(groups[0].failed).toBe(1)
    expect(groups[0].passed).toBe(1)
    expect(groups[1].failed).toBe(0)
    expect(groups[1].passed).toBe(2)
  })

  it('skips blocked minions', () => {
    const blockedMsg = 'The function "state.apply" is running as PID 1234'
    const groups = groupByState([
      minion('a', ok('one')),
      minion('b', [blockedMsg], false),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].outcomes).toHaveLength(1)
    expect(groups[0].outcomes[0].minion).toBe('a')
  })

  it('counts test-mode results separately', () => {
    const groups = groupByState([
      minion('a', testMode('dryrun')),
      minion('b', testMode('dryrun')),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].testMode).toBe(2)
    expect(groups[0].failed).toBe(0)
    expect(groups[0].passed).toBe(0)
  })

  it('orders outcomes within a group: failed → with-changes → alpha', () => {
    const groups = groupByState([
      minion('charlie', okChanged('s')),
      minion('alice', failed('s')),
      minion('bravo', ok('s')),
      minion('delta', okChanged('s')),
    ])
    expect(groups[0].outcomes.map((o) => o.minion))
      .toEqual(['alice', 'charlie', 'delta', 'bravo'])
  })
})

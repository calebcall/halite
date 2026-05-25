// frontend/tests/highstate-parse.test.ts
import { describe, expect, it } from 'vitest'

import { hasChanges, parseHighstate, summarize } from '@/features/jobs/highstate/parse'

const happyResult = {
  'pkg_|-install_nginx_|-nginx_|-installed': {
    name: 'nginx',
    changes: { nginx: { old: '', new: '1.18.0' } },
    result: true,
    comment: 'Package nginx is installed',
    duration: 234.5,
    __run_num__: 0,
    __sls__: 'webserver',
    start_time: '12:34:56.123456',
  },
  'service_|-nginx_running_|-nginx_|-running': {
    name: 'nginx',
    changes: {},
    result: true,
    comment: 'Service is already running',
    duration: 12.3,
    __run_num__: 1,
    __sls__: 'webserver',
    start_time: '12:34:56.357956',
  },
}

describe('parseHighstate', () => {
  it('parses a happy two-state highstate result', () => {
    const parsed = parseHighstate(happyResult)
    expect(parsed).not.toBeNull()
    expect(parsed).toHaveLength(2)
    expect(parsed?.[0]).toMatchObject({
      module: 'pkg',
      stateId: 'install_nginx',
      name: 'nginx',
      fun: 'installed',
      result: true,
      runNum: 0,
    })
    expect(parsed?.[1].fun).toBe('running')
  })

  it('sorts by __run_num__ regardless of dict iteration order', () => {
    const out = parseHighstate({
      'a_|-late_|-x_|-installed': { result: true, comment: '', __run_num__: 5 },
      'a_|-early_|-x_|-installed': { result: true, comment: '', __run_num__: 1 },
      'a_|-mid_|-x_|-installed': { result: true, comment: '', __run_num__: 3 },
    })
    expect(out?.map((s) => s.stateId)).toEqual(['early', 'mid', 'late'])
  })

  it('returns null for a regular minion-result dict', () => {
    expect(parseHighstate({ 'web-01': { foo: 'bar' } })).toBeNull()
  })

  it('returns null for an empty dict', () => {
    expect(parseHighstate({})).toBeNull()
  })

  it('returns null for a string (e.g. cmd.run output)', () => {
    expect(parseHighstate('hello\nworld')).toBeNull()
  })

  it('returns null for null / undefined / number / array', () => {
    expect(parseHighstate(null)).toBeNull()
    expect(parseHighstate(undefined)).toBeNull()
    expect(parseHighstate(42)).toBeNull()
    expect(parseHighstate([1, 2, 3])).toBeNull()
  })

  it('returns null if any key fails the low-state regex', () => {
    const mixed = {
      ...happyResult,
      'not-a-lowstate-key': { result: true, comment: '' },
    }
    expect(parseHighstate(mixed)).toBeNull()
  })

  it('returns null if a value lacks result or comment', () => {
    expect(
      parseHighstate({
        'pkg_|-x_|-y_|-installed': { result: true /* no comment */ },
      }),
    ).toBeNull()
  })

  it('handles test-mode result=null cleanly', () => {
    const out = parseHighstate({
      'pkg_|-x_|-y_|-installed': {
        result: null,
        comment: 'Would install',
        changes: { y: { new: '1.0' } },
        __run_num__: 0,
      },
    })
    expect(out?.[0].result).toBeNull()
  })

  it('coerces non-string comment to string', () => {
    const out = parseHighstate({
      'pkg_|-x_|-y_|-installed': {
        result: false,
        comment: 42 as unknown as string,
        __run_num__: 0,
      },
    })
    expect(out?.[0].comment).toBe('42')
  })
})

describe('hasChanges', () => {
  it('true when changes is a non-empty object', () => {
    expect(hasChanges({ ...stub(), changes: { foo: 'bar' } })).toBe(true)
  })
  it('false when changes is an empty object', () => {
    expect(hasChanges({ ...stub(), changes: {} })).toBe(false)
  })
  it('false when changes is undefined', () => {
    expect(hasChanges({ ...stub(), changes: undefined })).toBe(false)
  })
  it('true when changes is a non-empty array', () => {
    expect(hasChanges({ ...stub(), changes: ['x'] })).toBe(true)
  })
})

describe('summarize', () => {
  it('counts states, with-changes, failed, and sums duration', () => {
    const states = parseHighstate({
      'pkg_|-a_|-a_|-installed': { result: true, comment: '', changes: { a: 1 }, duration: 100, __run_num__: 0 },
      'pkg_|-b_|-b_|-installed': { result: true, comment: '', changes: {}, duration: 50, __run_num__: 1 },
      'pkg_|-c_|-c_|-installed': { result: false, comment: 'failed', changes: {}, duration: 200, __run_num__: 2 },
    })!
    const stats = summarize(states)
    expect(stats).toEqual({ total: 3, withChanges: 1, failed: 1, totalDurationMs: 350 })
  })

  it('handles empty list', () => {
    expect(summarize([])).toEqual({ total: 0, withChanges: 0, failed: 0, totalDurationMs: 0 })
  })
})

function stub() {
  return {
    module: 'pkg', stateId: 'x', name: 'y', fun: 'installed',
    result: true as boolean | null, comment: '', changes: undefined,
    duration: null, runNum: 0, sls: null, startTime: null,
  }
}

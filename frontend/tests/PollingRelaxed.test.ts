import { readFileSync } from 'node:fs'
import { describe, it, expect } from 'vitest'

const files = [
  'src/features/jobs/use-jobs.ts',
  'src/features/minions/use-minions.ts',
  'src/features/keys/use-keys.ts',
]

describe('polling relaxed in favor of the event stream', () => {
  it('has no 30s refetchInterval left in live-list hooks', () => {
    for (const f of files) {
      const src = readFileSync(f, 'utf8')
      expect(src.includes('refetchInterval: 30_000')).toBe(false)
    }
  })
})

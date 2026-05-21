// frontend/src/features/minions/api.ts
import { api } from '@/shared/api/client'

export type MinionListOut = Awaited<ReturnType<typeof api.minions.list>>
export type MinionSummary = MinionListOut['minions'][number]

export const minionsQueryKeys = {
  all: ['minions'] as const,
  list: ['minions', 'list'] as const,
}

export const minionsApi = {
  list: api.minions.list,
}

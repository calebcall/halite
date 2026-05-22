// frontend/src/features/keys/api.ts
import { api } from '@/shared/api/client'

export type KeysListOut = Awaited<ReturnType<typeof api.keys.list>>
export type KeyEntry = KeysListOut['keys'][number]
export type KeyStatus = KeyEntry['status']

export const keysQueryKeys = {
  all: ['keys'] as const,
  list: ['keys', 'list'] as const,
}

export const keysApi = {
  list: api.keys.list,
  accept: api.keys.accept,
  reject: api.keys.reject,
  delete: api.keys.delete,
}

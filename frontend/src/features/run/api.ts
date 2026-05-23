// frontend/src/features/run/api.ts
import { api } from '@/shared/api/client'

export type RunCommandIn = Parameters<typeof api.run.post>[0]
export type RunCommandOut = Awaited<ReturnType<typeof api.run.post>>

export const runApi = {
  post: api.run.post,
}

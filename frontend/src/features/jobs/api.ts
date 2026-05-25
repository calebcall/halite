// frontend/src/features/jobs/api.ts
import { api } from '@/shared/api/client'

export type JobsListOut = Awaited<ReturnType<typeof api.jobs.list>>
export type JobSummary = JobsListOut['jobs'][number]
export type JobDetail = Awaited<ReturnType<typeof api.jobs.get>>
export type JobMinionResult = JobDetail['results'][number]

export const jobsQueryKeys = {
  all: ['jobs'] as const,
  detail: (jid: string) => ['jobs', 'detail', jid] as const,
  list: (limit?: number) => ['jobs', 'list', limit] as const,
}

export const jobsApi = {
  get: api.jobs.get,
  kill: api.jobs.kill,
  list: api.jobs.list,
}

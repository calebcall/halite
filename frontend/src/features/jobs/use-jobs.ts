// frontend/src/features/jobs/use-jobs.ts
import { useQuery } from '@tanstack/react-query'

import { type JobDetail, type JobsListOut, jobsApi, jobsQueryKeys } from './api'

export function useJobsList(limit?: number) {
  return useQuery<JobsListOut>({
    queryFn: () => jobsApi.list(limit !== undefined ? { limit } : undefined),
    queryKey: jobsQueryKeys.list(limit),
    refetchInterval: 30_000,
  })
}

export function useJob(jid: string) {
  return useQuery<JobDetail>({
    queryFn: () => jobsApi.get(jid),
    queryKey: jobsQueryKeys.detail(jid),
  })
}

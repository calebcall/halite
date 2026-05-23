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
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) {
        return false
      }
      // Salt populates `minions` upfront when the job is dispatched, and
      // appends to `results` as each minion replies. Poll while incomplete.
      if (data.results.length < data.minions.length) {
        return 3_000
      }
      return false
    },
    staleTime: 5 * 60 * 1000,
  })
}

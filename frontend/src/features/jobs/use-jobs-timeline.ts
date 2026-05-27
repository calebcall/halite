// frontend/src/features/jobs/use-jobs-timeline.ts
import { useQuery } from '@tanstack/react-query'

import { api } from '@/shared/api/client'

type TimelineParams = Parameters<typeof api.jobs.timeline>[0]

export function useJobsTimeline(params: TimelineParams = {}) {
  return useQuery({
    queryFn: () => api.jobs.timeline(params),
    queryKey: ['jobs', 'timeline', params] as const,
    refetchInterval: 5 * 60 * 1000,
    refetchOnWindowFocus: true,
    staleTime: 30_000,
  })
}

import { useQuery } from '@tanstack/react-query'

import { api } from '@/shared/api/client'

export function useMinionRuns(minionId: string, limit = 20) {
  return useQuery({
    queryFn: () => api.minions.runs(minionId, { limit }),
    queryKey: ['minions', minionId, 'runs', limit] as const,
    refetchInterval: 5 * 60 * 1000,
    refetchOnWindowFocus: true,
    staleTime: 30_000,
  })
}

export function useMinionCompliance(minionId: string, limit = 30) {
  return useQuery({
    queryFn: () => api.minions.compliance(minionId, { limit }),
    queryKey: ['minions', minionId, 'compliance', limit] as const,
    refetchInterval: 5 * 60 * 1000,
    refetchOnWindowFocus: true,
    staleTime: 30_000,
  })
}

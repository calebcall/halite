// frontend/src/features/fleet/use-fleet.ts
import { useQuery } from '@tanstack/react-query'

import { api } from '@/shared/api/client'

export const fleetKeys = {
  all: ['fleet'] as const,
  compliance: (limit: number) => [...fleetKeys.all, 'compliance', limit] as const,
  health: () => [...fleetKeys.all, 'health'] as const,
  run: (id: string) => [...fleetKeys.all, 'run', id] as const,
  topFailures: (limit: number) => [...fleetKeys.all, 'top-failures', limit] as const,
}

const REFETCH_MS = 60_000

export function useFleetHealth() {
  return useQuery({
    queryFn: () => api.fleet.health(),
    queryKey: fleetKeys.health(),
    refetchInterval: REFETCH_MS,
    refetchOnWindowFocus: true,
  })
}

export function useFleetCompliance(limit = 30) {
  return useQuery({
    queryFn: () => api.fleet.compliance(limit),
    queryKey: fleetKeys.compliance(limit),
    refetchInterval: REFETCH_MS,
  })
}

export function useFleetTopFailures(limit = 10) {
  return useQuery({
    queryFn: () => api.fleet.topFailures(limit),
    queryKey: fleetKeys.topFailures(limit),
    refetchInterval: REFETCH_MS,
  })
}

export function useFleetRun(id: string | null) {
  return useQuery({
    enabled: id !== null,
    queryFn: () => api.fleet.runDetail(id as string),
    queryKey: fleetKeys.run(id ?? ''),
  })
}

// frontend/src/features/admin/use-settings.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/shared/api/client'
import { widgetConfigQueryKey } from '@/features/activity/use-widget-config'

export const settingsKeys = {
  all: ['settings'] as const,
  full: () => [...settingsKeys.all, 'full'] as const,
  status: () => [...settingsKeys.all, 'status'] as const,
}

export function useSettings() {
  return useQuery({
    queryFn: () => api.settings.get(),
    queryKey: settingsKeys.full(),
    staleTime: 30_000,
  })
}

export function useSettingsStatus() {
  return useQuery({
    queryFn: () => api.settings.status(),
    queryKey: settingsKeys.status(),
    staleTime: 30_000,
  })
}

export function useTestSalt() {
  return useMutation({ mutationFn: api.settings.testSalt })
}

export function useTestSaltSaved() {
  return useMutation({ mutationFn: api.settings.testSaltSaved })
}

export function useUpdateLogging() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.settings.putLogging,
    // Returning the Promise makes mutateAsync wait for the active
    // settings queries to refetch before resolving — callers can
    // navigate immediately afterward without racing the cache.
    onSuccess: () => qc.invalidateQueries({ queryKey: settingsKeys.all }),
  })
}

export function useUpdatePollers() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.settings.putPollers,
    onSuccess: () => qc.invalidateQueries({ queryKey: settingsKeys.all }),
  })
}

export function useUpdateWidget() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.settings.putWidget,
    onSuccess: async () => {
      // Invalidate both the admin settings query AND the read-only widget
      // config query so the live Overview widget picks up the change.
      await Promise.all([
        qc.invalidateQueries({ queryKey: settingsKeys.all }),
        qc.invalidateQueries({ queryKey: widgetConfigQueryKey }),
      ])
    },
  })
}

export function useUpdateSalt() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.settings.putSalt,
    onSuccess: () => qc.invalidateQueries({ queryKey: settingsKeys.all }),
  })
}

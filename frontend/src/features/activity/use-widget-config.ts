import { useQuery } from '@tanstack/react-query'

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/types.gen'

export type WidgetConfigOut = components['schemas']['WidgetConfigOut']

export const widgetConfigQueryKey = ['activity', 'widget-config'] as const

export function useWidgetConfig() {
  return useQuery<WidgetConfigOut>({
    queryKey: widgetConfigQueryKey,
    queryFn: () => api.activity.widgetConfig(),
    staleTime: 60_000,
  })
}

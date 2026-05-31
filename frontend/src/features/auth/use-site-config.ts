import { useQuery } from '@tanstack/react-query'

import { authApi } from './api'

export function useSiteConfig() {
  return useQuery({
    queryKey: ['site', 'config'],
    queryFn: () => authApi.config(),
    staleTime: Infinity,
  })
}

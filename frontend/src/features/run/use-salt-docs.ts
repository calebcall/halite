// frontend/src/features/run/use-salt-docs.ts
import { useQuery } from '@tanstack/react-query'

import { api } from '@/shared/api/client'

export const saltDocsQueryKeys = {
  functions: ['salt', 'functions'] as const,
}

export function useSaltFunctions() {
  return useQuery({
    queryKey: saltDocsQueryKeys.functions,
    queryFn: () => api.salt.functions(),
    // Backend caches for 1 hour; frontend's 5-min staleTime avoids
    // refetching on every page navigation.
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  })
}

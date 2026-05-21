// frontend/src/features/minions/use-minions.ts
import { useQuery } from '@tanstack/react-query'

import { type MinionListOut, minionsApi, minionsQueryKeys } from './api'

export function useMinionsList() {
  return useQuery<MinionListOut>({
    queryKey: minionsQueryKeys.list,
    queryFn: () => minionsApi.list(),
    refetchInterval: 30_000,  // live-ish; real-time events come in a later plan
  })
}

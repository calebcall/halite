// frontend/src/features/minions/use-minions.ts
import { useQuery } from '@tanstack/react-query'

import { type MinionDetail, type MinionListOut, minionsApi, minionsQueryKeys } from './api'

export function useMinionsList() {
  return useQuery<MinionListOut>({
    queryKey: minionsQueryKeys.list,
    queryFn: () => minionsApi.list(),
    refetchInterval: 30_000,
  })
}

export function useMinion(minionId: string | undefined) {
  return useQuery<MinionDetail>({
    queryKey: minionId ? minionsQueryKeys.detail(minionId) : ['minions', 'detail', '__none__'],
    queryFn: () => minionsApi.get(minionId as string),
    enabled: !!minionId,
  })
}

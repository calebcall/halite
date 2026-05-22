// frontend/src/features/keys/use-keys.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { type KeysListOut, keysApi, keysQueryKeys } from './api'

export function useKeysList() {
  return useQuery<KeysListOut>({
    queryKey: keysQueryKeys.list,
    queryFn: () => keysApi.list(),
    refetchInterval: 30_000,
  })
}

export function useAcceptKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (keyId: string) => keysApi.accept(keyId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keysQueryKeys.all })
      void qc.invalidateQueries({ queryKey: ['minions'] })
    },
  })
}

export function useRejectKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (keyId: string) => keysApi.reject(keyId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keysQueryKeys.all })
      void qc.invalidateQueries({ queryKey: ['minions'] })
    },
  })
}

export function useDeleteKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (keyId: string) => keysApi.delete(keyId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keysQueryKeys.all })
      void qc.invalidateQueries({ queryKey: ['minions'] })
    },
  })
}

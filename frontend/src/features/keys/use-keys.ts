// frontend/src/features/keys/use-keys.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { type KeysListOut, keysApi, keysQueryKeys } from './api'
import { minionsQueryKeys } from '@/features/minions/api'

export function useKeysList() {
  return useQuery<KeysListOut>({
    queryKey: keysQueryKeys.list,
    queryFn: () => keysApi.list(),
    refetchInterval: 5 * 60 * 1000,
  })
}

export function useAcceptKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (keyId: string) => keysApi.accept(keyId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keysQueryKeys.all })
      // Accepting a key moves a minion into the connected list.
      void qc.invalidateQueries({ queryKey: minionsQueryKeys.all })
    },
  })
}

export function useRejectKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (keyId: string) => keysApi.reject(keyId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keysQueryKeys.all })
      // Rejecting may remove a previously-accepted minion from the connected list.
      void qc.invalidateQueries({ queryKey: minionsQueryKeys.all })
    },
  })
}

export function useDeleteKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (keyId: string) => keysApi.delete(keyId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keysQueryKeys.all })
      // Deleting the key removes any associated minion from the connected list.
      void qc.invalidateQueries({ queryKey: minionsQueryKeys.all })
    },
  })
}

// frontend/src/features/roles/use-roles.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  type RoleListOut,
  type RoleSummary,
  rolesApi,
  rolesQueryKeys,
} from './api'

// ---------- Queries ----------

export function useRolesList(limit = 50, offset = 0) {
  return useQuery<RoleListOut>({
    queryKey: rolesQueryKeys.list(limit, offset),
    queryFn: () => rolesApi.list({ limit, offset }),
  })
}

export function useRole(roleId: string | undefined) {
  return useQuery<RoleSummary>({
    queryKey: roleId ? rolesQueryKeys.detail(roleId) : ['roles', 'detail', '__none__'],
    queryFn: () => rolesApi.get(roleId as string),
    enabled: !!roleId,
  })
}

// ---------- Mutations ----------

export function useCreateRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: rolesApi.create,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: rolesQueryKeys.all })
    },
  })
}

export function useUpdateRole(roleId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Parameters<typeof rolesApi.update>[1]) => rolesApi.update(roleId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: rolesQueryKeys.all })
    },
  })
}

export function useDeleteRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (roleId: string) => rolesApi.delete(roleId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: rolesQueryKeys.all })
    },
  })
}

export function useAddPermission(roleId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Parameters<typeof rolesApi.addPermission>[1]) =>
      rolesApi.addPermission(roleId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: rolesQueryKeys.detail(roleId) })
      void qc.invalidateQueries({ queryKey: rolesQueryKeys.list(50, 0) })
    },
  })
}

export function useRemovePermission(roleId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (permissionId: string) => rolesApi.removePermission(roleId, permissionId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: rolesQueryKeys.detail(roleId) })
    },
  })
}

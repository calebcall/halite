// frontend/src/features/users/use-users.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  rolesApi,
  rolesQueryKeys,
  type UserListOut,
  type UserSummary,
  usersApi,
  usersQueryKeys,
} from './api'

// ---------- Queries ----------

export function useUsersList(limit = 25, offset = 0) {
  return useQuery<UserListOut>({
    queryKey: usersQueryKeys.list(limit, offset),
    queryFn: () => usersApi.list({ limit, offset }),
  })
}

export function useUser(userId: string | undefined) {
  return useQuery<UserSummary>({
    queryKey: userId ? usersQueryKeys.detail(userId) : ['users', 'detail', '__none__'],
    queryFn: () => usersApi.get(userId as string),
    enabled: !!userId,
  })
}

export function useUserRoles(userId: string | undefined) {
  return useQuery<string[]>({
    queryKey: userId ? usersQueryKeys.roles(userId) : ['users', 'roles', '__none__'],
    queryFn: () => usersApi.listRoles(userId as string),
    enabled: !!userId,
  })
}

export function useRolesList() {
  return useQuery({
    queryKey: rolesQueryKeys.list,
    queryFn: () => rolesApi.list({ limit: 500, offset: 0 }),
  })
}

// ---------- Mutations ----------

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: usersApi.create,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: usersQueryKeys.all })
    },
  })
}

export function useUpdateUser(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Parameters<typeof usersApi.update>[1]) => usersApi.update(userId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: usersQueryKeys.all })
    },
  })
}

export function useDeleteUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => usersApi.delete(userId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: usersQueryKeys.all })
    },
  })
}

export function useResetUserPassword(userId: string) {
  return useMutation({
    mutationFn: (body: Parameters<typeof usersApi.resetPassword>[1]) =>
      usersApi.resetPassword(userId, body),
  })
}

export function useAddUserRole(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (roleId: string) => usersApi.addRole(userId, { role_id: roleId }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: usersQueryKeys.roles(userId) })
    },
  })
}

export function useRemoveUserRole(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (roleId: string) => usersApi.removeRole(userId, roleId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: usersQueryKeys.roles(userId) })
    },
  })
}

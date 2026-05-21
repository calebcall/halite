// frontend/src/features/users/api.ts
import { api } from '@/shared/api/client'

export type UserSummary = Awaited<ReturnType<typeof api.users.get>>
export type UserListOut = Awaited<ReturnType<typeof api.users.list>>
export type RoleSummary = Awaited<ReturnType<typeof api.roles.get>>
export type RoleListOut = Awaited<ReturnType<typeof api.roles.list>>

export const usersQueryKeys = {
  all: ['users'] as const,
  list: (limit: number, offset: number) =>
    [...usersQueryKeys.all, 'list', { limit, offset }] as const,
  detail: (userId: string) => [...usersQueryKeys.all, 'detail', userId] as const,
  roles: (userId: string) => [...usersQueryKeys.all, 'roles', userId] as const,
}

export const rolesQueryKeys = {
  all: ['roles'] as const,
  list: ['roles', 'list'] as const,
}

export const usersApi = {
  list: api.users.list,
  get: api.users.get,
  create: api.users.create,
  update: api.users.update,
  delete: api.users.delete,
  resetPassword: api.users.resetPassword,
  listRoles: api.users.listRoles,
  addRole: api.users.addRole,
  removeRole: api.users.removeRole,
}

export const rolesApi = {
  list: api.roles.list,
  get: api.roles.get,
}

// frontend/src/features/roles/api.ts
import { api } from '@/shared/api/client'

export type RoleSummary = Awaited<ReturnType<typeof api.roles.get>>
export type RoleListOut = Awaited<ReturnType<typeof api.roles.list>>
export type PermissionOut = RoleSummary['permissions'][number]

export const rolesQueryKeys = {
  all: ['roles'] as const,
  list: (limit: number, offset: number) =>
    [...rolesQueryKeys.all, 'list', { limit, offset }] as const,
  detail: (roleId: string) => [...rolesQueryKeys.all, 'detail', roleId] as const,
}

export const rolesApi = {
  list: api.roles.list,
  get: api.roles.get,
  create: api.roles.create,
  update: api.roles.update,
  delete: api.roles.delete,
  addPermission: api.roles.addPermission,
  removePermission: api.roles.removePermission,
}

// frontend/src/features/audit/api.ts
import { api } from '@/shared/api/client'

export type AuditListOut = Awaited<ReturnType<typeof api.audit.list>>
export type AuditEntry = AuditListOut['entries'][number]
export type Decision = 'allow' | 'deny'

export interface AuditFilter {
  action?: string
  decision?: Decision
  since?: string  // ISO timestamp
  until?: string  // ISO timestamp
  limit: number
  offset: number
}

export const auditQueryKeys = {
  all: ['audit'] as const,
  list: (filter: AuditFilter) => [...auditQueryKeys.all, 'list', filter] as const,
}

export const auditApi = {
  list: api.audit.list,
}

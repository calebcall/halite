// frontend/src/features/audit/use-audit.ts
import { useQuery } from '@tanstack/react-query'

import { type AuditFilter, type AuditListOut, auditApi, auditQueryKeys } from './api'

export function useAuditList(filter: AuditFilter) {
  return useQuery<AuditListOut>({
    queryKey: auditQueryKeys.list(filter),
    queryFn: () =>
      auditApi.list({
        action: filter.action || undefined,
        decision: filter.decision || undefined,
        since: filter.since || undefined,
        until: filter.until || undefined,
        limit: filter.limit,
        offset: filter.offset,
      }),
    placeholderData: (prev) => prev, // keep prior data while filters change
  })
}

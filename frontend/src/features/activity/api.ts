// frontend/src/features/activity/api.ts
import { api } from '@/shared/api/client'

export type ActivityListOut = Awaited<ReturnType<typeof api.activity.list>>
export type ActivityEventOut = ActivityListOut['events'][number]

export interface ActivityFilter {
  category?: string
  minion_id?: string
  event_type?: string
  search?: string
  hide_routine?: boolean
  hide_dispatch?: boolean
  categories?: string
  since_minutes?: number
  limit?: number
  offset?: number
}

export const activityApi = {
  list: (f: ActivityFilter = {}) => api.activity.list(f),
}

export const activityQueryKeys = {
  all: ['activity'] as const,
  list: (f: ActivityFilter) => ['activity', 'list', f] as const,
}

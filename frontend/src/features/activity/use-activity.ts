import { useQuery } from '@tanstack/react-query'

import { activityApi, activityQueryKeys, type ActivityFilter, type ActivityListOut } from './api'

export function useActivityList(filter: ActivityFilter) {
  return useQuery<ActivityListOut>({
    queryKey: activityQueryKeys.list(filter),
    queryFn: () => activityApi.list(filter),
    placeholderData: (prev) => prev,
  })
}

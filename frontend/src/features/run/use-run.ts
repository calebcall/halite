// frontend/src/features/run/use-run.ts
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { jobsQueryKeys } from '@/features/jobs/api'
import { type RunCommandIn, type RunCommandOut, runApi } from './api'

export function useRunCommand() {
  const qc = useQueryClient()
  return useMutation<RunCommandOut, Error, RunCommandIn>({
    mutationFn: (body) => runApi.post(body),
    onSuccess: () => {
      // New job created — invalidate the jobs list so it shows on next visit.
      void qc.invalidateQueries({ queryKey: jobsQueryKeys.all })
    },
  })
}

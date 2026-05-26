// frontend/src/features/run/use-templates.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/shared/api/client'

export type CommandTemplate = Awaited<ReturnType<typeof api.templates.list>>['templates'][number]
export type CommandTemplateCreate = Parameters<typeof api.templates.create>[0]

export const templatesQueryKeys = {
  all: ['templates'] as const,
  list: ['templates', 'list'] as const,
}

export function useTemplates() {
  return useQuery({
    queryKey: templatesQueryKeys.list,
    queryFn: () => api.templates.list(),
    staleTime: 60 * 1000,
  })
}

export function useCreateTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CommandTemplateCreate) => api.templates.create(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: templatesQueryKeys.all })
    },
  })
}

export function useDeleteTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.templates.delete(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: templatesQueryKeys.all })
    },
  })
}

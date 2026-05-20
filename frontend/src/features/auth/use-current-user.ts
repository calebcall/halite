import { useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError } from '@/shared/api/client'
import { authApi, type CurrentUser } from './api'

const ME_QUERY_KEY = ['auth', 'me'] as const

export function useCurrentUser() {
  const query = useQuery<CurrentUser | null>({
    queryKey: ME_QUERY_KEY,
    queryFn: async () => {
      try {
        return await authApi.me()
      } catch (e) {
        if (e instanceof ApiError && e.isUnauthorized) return null
        throw e
      }
    },
  })
  return query
}

export function useAuthActions() {
  const qc = useQueryClient()
  return {
    async login(username: string, password: string) {
      const user = await authApi.login({ username, password })
      qc.setQueryData(ME_QUERY_KEY, user)
      return user
    },
    async logout() {
      await authApi.logout()
      qc.setQueryData(ME_QUERY_KEY, null)
      qc.clear()
      qc.setQueryData(ME_QUERY_KEY, null)
    },
  }
}

export function useChangePassword() {
  const qc = useQueryClient()
  return async function changePassword(currentPassword: string, newPassword: string) {
    await authApi.changePassword({
      current_password: currentPassword,
      new_password: newPassword,
    })
    // The backend cleared must_change_pw — refresh the cached me response so
    // the MustChangePassword guard releases the user back to the app.
    const fresh = await authApi.me()
    qc.setQueryData(ME_QUERY_KEY, fresh)
  }
}

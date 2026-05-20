import { api } from '@/shared/api/client'

export type CurrentUser = Awaited<ReturnType<typeof api.auth.me>>

export const authApi = {
  login: (body: { username: string; password: string }) => api.auth.login(body),
  logout: () => api.auth.logout(),
  me: () => api.auth.me(),
  changePassword: (body: { current_password: string; new_password: string }) =>
    api.auth.changePassword(body),
}

// frontend/src/shared/api/client.ts
import type { paths } from './types.gen'

export class ApiError extends Error {
  status: number
  body: unknown
  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `HTTP ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
  get isUnauthorized() {
    return this.status === 401
  }
  get isForbidden() {
    return this.status === 403
  }
}

type Method = 'GET' | 'POST' | 'PATCH' | 'DELETE'

interface RequestOpts {
  method: Method
  path: string
  body?: unknown
  query?: Record<string, string | number | boolean | undefined>
}

async function request<T>({ method, path, body, query }: RequestOpts): Promise<T> {
  const url = new URL(path, window.location.origin)
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined) url.searchParams.set(k, String(v))
    }
  }
  const init: RequestInit = {
    method,
    credentials: 'include', // send + accept the session cookie
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  }
  const res = await fetch(url.toString(), init)
  if (res.status === 204) return undefined as T
  const text = await res.text()
  const parsed = text.length > 0 ? safeJson(text) : undefined
  if (!res.ok) {
    throw new ApiError(res.status, parsed, extractDetail(parsed))
  }
  return parsed as T
}

function safeJson(text: string): unknown {
  try { return JSON.parse(text) } catch { return text }
}

function extractDetail(body: unknown): string | undefined {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as Record<string, unknown>).detail
    if (typeof detail === 'string') return detail
  }
  return undefined
}

export function errorDetail(e: unknown): string | null {
  if (e instanceof ApiError) {
    // ApiError.message was populated from body.detail by extractDetail; if
    // the body had no detail we get the default `HTTP ${status}` which
    // isn't useful as a detail line.
    if (e.message && !e.message.startsWith('HTTP ')) {
      return e.message
    }
  }
  return null
}

export const api = {
  auth: {
    login: (body: { username: string; password: string }) =>
      request<paths['/api/auth/login']['post']['responses']['200']['content']['application/json']>({
        method: 'POST',
        path: '/api/auth/login',
        body,
      }),
    logout: () => request<void>({ method: 'POST', path: '/api/auth/logout' }),
    me: () =>
      request<paths['/api/auth/me']['get']['responses']['200']['content']['application/json']>({
        method: 'GET',
        path: '/api/auth/me',
      }),
    changePassword: (body: { current_password: string; new_password: string }) =>
      request<void>({
        method: 'POST',
        path: '/api/auth/change-password',
        body,
      }),
  },
  users: {
    list: (query: { limit?: number; offset?: number } = {}) =>
      request<paths['/api/users']['get']['responses']['200']['content']['application/json']>({
        method: 'GET',
        path: '/api/users',
        query,
      }),
    get: (userId: string) =>
      request<paths['/api/users/{user_id}']['get']['responses']['200']['content']['application/json']>({
        method: 'GET',
        path: `/api/users/${encodeURIComponent(userId)}`,
      }),
    create: (
      body: paths['/api/users']['post']['requestBody']['content']['application/json'],
    ) =>
      request<paths['/api/users']['post']['responses']['201']['content']['application/json']>({
        method: 'POST',
        path: '/api/users',
        body,
      }),
    update: (
      userId: string,
      body: paths['/api/users/{user_id}']['patch']['requestBody']['content']['application/json'],
    ) =>
      request<paths['/api/users/{user_id}']['patch']['responses']['200']['content']['application/json']>({
        method: 'PATCH',
        path: `/api/users/${encodeURIComponent(userId)}`,
        body,
      }),
    delete: (userId: string) =>
      request<void>({
        method: 'DELETE',
        path: `/api/users/${encodeURIComponent(userId)}`,
      }),
    resetPassword: (
      userId: string,
      body: paths['/api/users/{user_id}/password']['post']['requestBody']['content']['application/json'],
    ) =>
      request<void>({
        method: 'POST',
        path: `/api/users/${encodeURIComponent(userId)}/password`,
        body,
      }),
    listRoles: (userId: string) =>
      request<paths['/api/users/{user_id}/roles']['get']['responses']['200']['content']['application/json']>({
        method: 'GET',
        path: `/api/users/${encodeURIComponent(userId)}/roles`,
      }),
    addRole: (
      userId: string,
      body: paths['/api/users/{user_id}/roles']['post']['requestBody']['content']['application/json'],
    ) =>
      request<void>({
        method: 'POST',
        path: `/api/users/${encodeURIComponent(userId)}/roles`,
        body,
      }),
    removeRole: (userId: string, roleId: string) =>
      request<void>({
        method: 'DELETE',
        path: `/api/users/${encodeURIComponent(userId)}/roles/${encodeURIComponent(roleId)}`,
      }),
  },
  audit: {
    list: (
      query: {
        user_id?: string
        action?: string
        decision?: string
        since?: string
        until?: string
        limit?: number
        offset?: number
      } = {},
    ) =>
      request<paths['/api/audit']['get']['responses']['200']['content']['application/json']>({
        method: 'GET',
        path: '/api/audit',
        query,
      }),
  },
  jobs: {
    list: (params?: { limit?: number }) =>
      request<paths['/api/jobs']['get']['responses']['200']['content']['application/json']>({
        method: 'GET',
        path: '/api/jobs',
        query: params,
      }),
    get: (jid: string) =>
      request<paths['/api/jobs/{jid}']['get']['responses']['200']['content']['application/json']>({
        method: 'GET',
        path: `/api/jobs/${encodeURIComponent(jid)}`,
      }),
  },
  keys: {
    list: () =>
      request<paths['/api/keys']['get']['responses']['200']['content']['application/json']>({
        method: 'GET',
        path: '/api/keys',
      }),
    accept: (keyId: string) =>
      request<void>({
        method: 'POST',
        path: `/api/keys/${encodeURIComponent(keyId)}/accept`,
      }),
    reject: (keyId: string) =>
      request<void>({
        method: 'POST',
        path: `/api/keys/${encodeURIComponent(keyId)}/reject`,
      }),
    delete: (keyId: string) =>
      request<void>({
        method: 'DELETE',
        path: `/api/keys/${encodeURIComponent(keyId)}`,
      }),
  },
  roles: {
    list: (query: { limit?: number; offset?: number } = {}) =>
      request<paths['/api/roles']['get']['responses']['200']['content']['application/json']>({
        method: 'GET',
        path: '/api/roles',
        query,
      }),
    get: (roleId: string) =>
      request<paths['/api/roles/{role_id}']['get']['responses']['200']['content']['application/json']>({
        method: 'GET',
        path: `/api/roles/${encodeURIComponent(roleId)}`,
      }),
    create: (
      body: paths['/api/roles']['post']['requestBody']['content']['application/json'],
    ) =>
      request<paths['/api/roles']['post']['responses']['201']['content']['application/json']>({
        method: 'POST',
        path: '/api/roles',
        body,
      }),
    update: (
      roleId: string,
      body: paths['/api/roles/{role_id}']['patch']['requestBody']['content']['application/json'],
    ) =>
      request<paths['/api/roles/{role_id}']['patch']['responses']['200']['content']['application/json']>({
        method: 'PATCH',
        path: `/api/roles/${encodeURIComponent(roleId)}`,
        body,
      }),
    delete: (roleId: string) =>
      request<void>({
        method: 'DELETE',
        path: `/api/roles/${encodeURIComponent(roleId)}`,
      }),
    addPermission: (
      roleId: string,
      body: paths['/api/roles/{role_id}/permissions']['post']['requestBody']['content']['application/json'],
    ) =>
      request<paths['/api/roles/{role_id}/permissions']['post']['responses']['201']['content']['application/json']>({
        method: 'POST',
        path: `/api/roles/${encodeURIComponent(roleId)}/permissions`,
        body,
      }),
    removePermission: (roleId: string, permissionId: string) =>
      request<void>({
        method: 'DELETE',
        path: `/api/roles/${encodeURIComponent(roleId)}/permissions/${encodeURIComponent(permissionId)}`,
      }),
  },
  minions: {
    list: () =>
      request<paths['/api/minions']['get']['responses']['200']['content']['application/json']>({
        method: 'GET',
        path: '/api/minions',
      }),
    get: (minionId: string) =>
      request<paths['/api/minions/{minion_id}']['get']['responses']['200']['content']['application/json']>({
        method: 'GET',
        path: `/api/minions/${encodeURIComponent(minionId)}`,
      }),
  },
  run: {
    post: (body: paths['/api/run']['post']['requestBody']['content']['application/json']) =>
      request<paths['/api/run']['post']['responses']['202']['content']['application/json']>({
        method: 'POST',
        path: '/api/run',
        body,
      }),
  },
}

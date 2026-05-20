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
}

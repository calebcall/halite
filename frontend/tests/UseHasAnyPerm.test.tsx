// frontend/tests/UseHasAnyPerm.test.tsx
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { useHasAnyPerm } from '@/features/auth/use-has-perm'

const server = setupServer()

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  return { wrapper }
}

describe('useHasAnyPerm', () => {
  it('returns true when user has a matching permission in the list', async () => {
    server.use(
      http.get('/api/auth/me', () =>
        HttpResponse.json({
          username: 'alice',
          display_name: 'Alice',
          must_change_pw: false,
          permissions: [{ verb: 'view', resource_glob: 'key:*' }],
        }),
      ),
    )
    const { wrapper } = wrap()
    const { result } = renderHook(
      () =>
        useHasAnyPerm([
          { verb: 'view', resource: 'job:*' },
          { verb: 'view', resource: 'key:*' },
        ]),
      { wrapper },
    )
    await waitFor(() => expect(result.current).toBe(true))
  })

  it('returns false when user has no permission matching any pair', async () => {
    server.use(
      http.get('/api/auth/me', () =>
        HttpResponse.json({
          username: 'alice',
          display_name: 'Alice',
          must_change_pw: false,
          permissions: [{ verb: 'view', resource_glob: 'key:*' }],
        }),
      ),
    )
    const { wrapper } = wrap()
    const { result } = renderHook(
      () =>
        useHasAnyPerm([
          { verb: 'view', resource: 'user:*' },
        ]),
      { wrapper },
    )
    await waitFor(() => expect(result.current).toBe(false))
  })

  it('returns false for an empty pairs array', async () => {
    server.use(
      http.get('/api/auth/me', () =>
        HttpResponse.json({
          username: 'alice',
          display_name: 'Alice',
          must_change_pw: false,
          permissions: [{ verb: 'view', resource_glob: 'job:*' }],
        }),
      ),
    )
    const { wrapper } = wrap()
    const { result } = renderHook(() => useHasAnyPerm([]), { wrapper })
    // Initially false (no data); after load still false because pairs is empty.
    // Give it a tick to resolve, then assert.
    await waitFor(() => expect(result.current).toBe(false))
  })
})

// frontend/tests/AuditViewerPage.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { AuditViewerPage } from '@/features/audit/audit-viewer-page'

let lastQuery: URLSearchParams | null = null

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin',
      display_name: 'admin',
      must_change_pw: false,
      permissions: [{ verb: 'view', resource_glob: 'audit:*' }],
    }),
  ),
  http.get('/api/audit', ({ request }) => {
    lastQuery = new URL(request.url).searchParams
    const decision = lastQuery.get('decision')
    const entries = [
      {
        id: 1,
        at: '2026-05-21T10:00:00Z',
        user_id: '00000000-0000-0000-0000-000000000001',
        action: 'auth.login',
        resource: 'user:admin',
        args_json: null,
        salt_jid: null,
        decision: 'allow',
        result_code: 200,
        duration_ms: 12,
      },
      {
        id: 2,
        at: '2026-05-21T09:55:00Z',
        user_id: '00000000-0000-0000-0000-000000000002',
        action: 'user.delete',
        resource: 'user:bob',
        args_json: null,
        salt_jid: null,
        decision: 'deny',
        result_code: 403,
        duration_ms: 5,
      },
    ]
    const filtered = decision ? entries.filter((e) => e.decision === decision) : entries
    return HttpResponse.json({ total: filtered.length, entries: filtered })
  }),
)

beforeAll(() => server.listen())
afterEach(() => {
  server.resetHandlers()
  lastQuery = null
})
afterAll(() => server.close())

function renderInRouter() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const rootRoute = createRootRoute({ component: Outlet })
  const homeRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    component: () => <AuditViewerPage />,
  })
  const router = createRouter({ routeTree: rootRoute.addChildren([homeRoute]) })
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('AuditViewerPage', () => {
  it('renders the audit entries', async () => {
    renderInRouter()
    expect(await screen.findByText('auth.login')).toBeInTheDocument()
    expect(screen.getByText('user.delete')).toBeInTheDocument()
    expect(screen.getByText('user:admin')).toBeInTheDocument()
    expect(screen.getByText('user:bob')).toBeInTheDocument()
    expect(screen.getByText('allow')).toBeInTheDocument()
    expect(screen.getByText('deny')).toBeInTheDocument()
  })

  it('passes the decision filter to the API', async () => {
    const user = userEvent.setup()
    renderInRouter()
    await screen.findByText('auth.login')

    await user.selectOptions(screen.getByLabelText(/decision/i), 'deny')

    await waitFor(() => {
      expect(lastQuery?.get('decision')).toBe('deny')
    })
    // only the deny row should remain
    expect(screen.queryByText('auth.login')).not.toBeInTheDocument()
    expect(screen.getByText('user.delete')).toBeInTheDocument()
  })

  it('shows Forbidden on 403', async () => {
    server.use(
      http.get('/api/audit', () => HttpResponse.json({ detail: 'Forbidden' }, { status: 403 })),
    )
    renderInRouter()
    expect(await screen.findByText(/don'?t have permission/i)).toBeInTheDocument()
  })
})

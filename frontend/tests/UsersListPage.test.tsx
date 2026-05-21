// frontend/tests/UsersListPage.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { UsersListPage } from '@/features/users/users-list-page'

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({ username: 'admin', display_name: 'admin', must_change_pw: false }),
  ),
  http.get('/api/users', () =>
    HttpResponse.json({
      total: 2,
      users: [
        {
          id: '00000000-0000-0000-0000-000000000001',
          username: 'admin',
          display_name: 'Admin',
          email: null,
          is_active: true,
          is_builtin: true,
          must_change_pw: false,
          created_at: '2026-05-19T00:00:00Z',
          last_login_at: null,
        },
        {
          id: '00000000-0000-0000-0000-000000000002',
          username: 'alice',
          display_name: 'Alice',
          email: 'alice@example.com',
          is_active: false,
          is_builtin: false,
          must_change_pw: true,
          created_at: '2026-05-19T00:00:00Z',
          last_login_at: null,
        },
      ],
    }),
  ),
  http.get('/api/roles', () => HttpResponse.json({ total: 0, roles: [] })),
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function renderInRouter() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const rootRoute = createRootRoute({ component: Outlet })
  const homeRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    component: () => <UsersListPage />,
  })
  const router = createRouter({ routeTree: rootRoute.addChildren([homeRoute]) })
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('UsersListPage', () => {
  it('renders the users from the API', async () => {
    renderInRouter()
    expect(await screen.findByText('admin')).toBeInTheDocument()
    expect(screen.getByText('alice')).toBeInTheDocument()
    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(screen.getByText('Inactive')).toBeInTheDocument()
    expect(screen.getByText('built-in')).toBeInTheDocument()
  })

  it('shows Forbidden when the API returns 403', async () => {
    server.use(
      http.get('/api/users', () => HttpResponse.json({ detail: 'Forbidden' }, { status: 403 })),
    )
    renderInRouter()
    expect(await screen.findByText(/don'?t have permission/i)).toBeInTheDocument()
  })
})

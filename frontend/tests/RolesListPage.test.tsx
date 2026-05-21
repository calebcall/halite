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

import { RolesListPage } from '@/features/roles/roles-list-page'

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({ username: 'admin', display_name: 'admin', must_change_pw: false }),
  ),
  http.get('/api/roles', () =>
    HttpResponse.json({
      total: 2,
      roles: [
        {
          id: '11111111-1111-1111-1111-111111111111',
          name: 'admin',
          description: 'Full access',
          is_builtin: true,
        },
        {
          id: '22222222-2222-2222-2222-222222222222',
          name: 'operator',
          description: 'Runs salt commands',
          is_builtin: false,
        },
      ],
    }),
  ),
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
    component: () => <RolesListPage />,
  })
  const router = createRouter({ routeTree: rootRoute.addChildren([homeRoute]) })
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('RolesListPage', () => {
  it('renders roles from the API', async () => {
    renderInRouter()
    expect(await screen.findByText('admin')).toBeInTheDocument()
    expect(screen.getByText('operator')).toBeInTheDocument()
    expect(screen.getByText('Full access')).toBeInTheDocument()
    expect(screen.getByText('built-in')).toBeInTheDocument()
  })

  it('shows Forbidden on 403', async () => {
    server.use(
      http.get('/api/roles', () => HttpResponse.json({ detail: 'Forbidden' }, { status: 403 })),
    )
    renderInRouter()
    expect(await screen.findByText(/don'?t have permission/i)).toBeInTheDocument()
  })
})

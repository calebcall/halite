// frontend/tests/MinionsListPage.test.tsx
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

import { MinionsListPage } from '@/features/minions/minions-list-page'

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin',
      display_name: 'admin',
      must_change_pw: false,
      permissions: [{ verb: 'view', resource_glob: 'minion:*' }],
    }),
  ),
  http.get('/api/minions', () =>
    HttpResponse.json({
      total: 3,
      minions: [
        { id: 'db-01', ip: null, status: 'offline' },
        { id: 'pending-host', ip: null, status: 'pending' },
        { id: 'web-01', ip: '10.0.0.1', status: 'online' },
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
    component: () => <MinionsListPage />,
  })
  const router = createRouter({ routeTree: rootRoute.addChildren([homeRoute]) })
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('MinionsListPage', () => {
  it('renders minions with status badges', async () => {
    renderInRouter()
    expect(await screen.findByText('db-01')).toBeInTheDocument()
    expect(screen.getByText('pending-host')).toBeInTheDocument()
    expect(screen.getByText('web-01')).toBeInTheDocument()
    expect(screen.getByText('10.0.0.1')).toBeInTheDocument()
    expect(screen.getByText('online')).toBeInTheDocument()
    expect(screen.getByText('offline')).toBeInTheDocument()
    expect(screen.getByText('pending')).toBeInTheDocument()
  })

  it('shows the not-configured message on 503', async () => {
    server.use(
      http.get('/api/minions', () =>
        HttpResponse.json({ detail: 'Salt-API is not configured' }, { status: 503 }),
      ),
    )
    renderInRouter()
    expect(await screen.findByText(/salt-api is not configured/i)).toBeInTheDocument()
  })

  it('shows Forbidden on 403', async () => {
    server.use(
      http.get('/api/minions', () => HttpResponse.json({ detail: 'Forbidden' }, { status: 403 })),
    )
    renderInRouter()
    expect(await screen.findByText(/don'?t have permission/i)).toBeInTheDocument()
  })
})

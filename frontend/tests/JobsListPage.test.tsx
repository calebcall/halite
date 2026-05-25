// frontend/tests/JobsListPage.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { JobsListPage } from '@/features/jobs/jobs-list-page'

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin',
      display_name: 'admin',
      must_change_pw: false,
      permissions: [{ verb: 'view', resource_glob: 'job:*' }],
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
    component: () => <JobsListPage />,
  })
  const detailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/jobs/$jid',
    component: () => <div>detail-stub</div>,
  })
  const router = createRouter({ routeTree: rootRoute.addChildren([homeRoute, detailRoute]) })
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('JobsListPage', () => {
  it('renders recent jobs with their function and target', async () => {
    server.use(
      http.get('/api/jobs', () =>
        HttpResponse.json({
          total: 2,
          jobs: [
            {
              jid: '20251019120000123456', function: 'test.ping', target: '*',
              target_type: 'glob', user: 'halite-service', start_time: '2025-10-19T12:00:00',
              status: 'running',
            },
            {
              jid: '20251019110000000000', function: 'cmd.run', target: 'web-01',
              target_type: 'glob', user: 'halite-service', start_time: '2025-10-19T11:00:00',
              status: 'complete',
            },
          ],
        }),
      ),
    )
    renderInRouter()
    expect(await screen.findByText('20251019120000123456')).toBeInTheDocument()
    expect(screen.getByText('test.ping')).toBeInTheDocument()
    expect(screen.getByText('cmd.run')).toBeInTheDocument()
    expect(screen.getByText('running')).toBeInTheDocument()
    expect(screen.getByText('complete')).toBeInTheDocument()
  })

  it('filters jobs by function name', async () => {
    server.use(
      http.get('/api/jobs', () =>
        HttpResponse.json({
          total: 3,
          jobs: [
            { jid: 'j1', function: 'test.ping', target: '*', target_type: 'glob', user: 'a', start_time: '2025-10-19T12:00:00', status: 'complete' },
            { jid: 'j2', function: 'cmd.run', target: 'web-*', target_type: 'glob', user: 'a', start_time: '2025-10-19T11:00:00', status: 'complete' },
            { jid: 'j3', function: 'state.apply', target: 'db-*', target_type: 'glob', user: 'a', start_time: '2025-10-19T10:00:00', status: 'running' },
          ],
        }),
      ),
    )
    const user = userEvent.setup()
    renderInRouter()
    await screen.findByText('cmd.run')
    await user.type(screen.getByPlaceholderText(/filter by jid/i), 'state')
    expect(screen.queryByText('test.ping')).not.toBeInTheDocument()
    expect(screen.queryByText('cmd.run')).not.toBeInTheDocument()
    expect(screen.getByText('state.apply')).toBeInTheDocument()
    expect(screen.getByText(/Showing 1 of 3/i)).toBeInTheDocument()
  })

  it('shows the empty state when no jobs', async () => {
    server.use(
      http.get('/api/jobs', () => HttpResponse.json({ total: 0, jobs: [] })),
    )
    renderInRouter()
    expect(await screen.findByText(/no jobs in the master cache/i)).toBeInTheDocument()
  })

  it('shows Salt-API not configured on 503', async () => {
    server.use(
      http.get('/api/jobs', () => HttpResponse.json({ detail: 'no salt' }, { status: 503 })),
    )
    renderInRouter()
    expect(await screen.findByText(/salt-api is not configured/i)).toBeInTheDocument()
  })
})

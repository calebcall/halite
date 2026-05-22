// frontend/tests/JobDetailPage.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory,
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

import { JobDetailPage } from '@/features/jobs/job-detail-page'

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

function renderAt(jid: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const rootRoute = createRootRoute({ component: Outlet })
  const appRoute = createRoute({
    getParentRoute: () => rootRoute,
    id: 'app',
    component: Outlet,
  })
  const jobsRoute = createRoute({
    getParentRoute: () => appRoute,
    path: '/jobs',
    component: () => <div>jobs-list-stub</div>,
  })
  const detailRoute = createRoute({
    getParentRoute: () => appRoute,
    path: '/jobs/$jid',
    component: () => <JobDetailPage />,
  })
  const router = createRouter({
    routeTree: rootRoute.addChildren([appRoute.addChildren([jobsRoute, detailRoute])]),
    history: createMemoryHistory({ initialEntries: [`/jobs/${jid}`] }),
  })
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('JobDetailPage', () => {
  it('renders job metadata + per-minion results', async () => {
    server.use(
      http.get('/api/jobs/:jid', () =>
        HttpResponse.json({
          jid: '20251019120000123456',
          function: 'test.ping',
          arguments: [],
          target: '*',
          target_type: 'glob',
          user: 'halite-service',
          start_time: '2025-10-19T12:00:00',
          minions: ['web-01', 'web-02'],
          results: [
            { minion: 'web-01', success: true, retcode: 0, return_value: true },
            { minion: 'web-02', success: false, retcode: 1, return_value: 'perm denied' },
          ],
        }),
      ),
    )
    renderAt('20251019120000123456')
    expect(await screen.findByText('20251019120000123456')).toBeInTheDocument()
    expect(screen.getByText(/test\.ping on \*/i)).toBeInTheDocument()
    expect(screen.getByText('web-01')).toBeInTheDocument()
    expect(screen.getByText('web-02')).toBeInTheDocument()
    expect(screen.getByText('success')).toBeInTheDocument()
    expect(screen.getByText('failed')).toBeInTheDocument()
  })

  it('expands a minion result on click', async () => {
    server.use(
      http.get('/api/jobs/:jid', () =>
        HttpResponse.json({
          jid: 'j1',
          function: 'test.ping',
          arguments: [],
          target: '*',
          target_type: 'glob',
          user: 'halite-service',
          start_time: '2025-10-19T12:00:00',
          minions: ['web-01'],
          results: [{ minion: 'web-01', success: true, retcode: 0, return_value: { ok: 1 } }],
        }),
      ),
    )
    const user = userEvent.setup()
    renderAt('j1')
    const trigger = await screen.findByRole('button', { name: /web-01/i })
    await user.click(trigger)
    expect(screen.getByText(/"ok": 1/)).toBeInTheDocument()
  })

  it('shows a 404 panel for unknown jids', async () => {
    server.use(
      http.get('/api/jobs/:jid', () => HttpResponse.json({ detail: 'not found' }, { status: 404 })),
    )
    renderAt('nonexistent')
    expect(await screen.findByText(/is not in the master cache/i)).toBeInTheDocument()
  })
})

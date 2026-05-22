// frontend/tests/MinionDetailPage.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory,
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

import { MinionDetailPage } from '@/features/minions/minion-detail-page'

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin',
      display_name: 'admin',
      must_change_pw: false,
      permissions: [{ verb: 'view', resource_glob: 'minion:*' }],
    }),
  ),
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

// Build a router whose route id matches the production id
// ('/app/minions/$minionId') so useParams({ from: ... }) inside the page resolves.
function renderDetail(minionId: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const rootRoute = createRootRoute({ component: Outlet })
  const appRoute = createRoute({
    getParentRoute: () => rootRoute,
    id: 'app',
    component: Outlet,
  })
  const detailRoute = createRoute({
    getParentRoute: () => appRoute,
    path: '/minions/$minionId',
    component: () => <MinionDetailPage />,
  })
  const tree = rootRoute.addChildren([appRoute.addChildren([detailRoute])])
  const router = createRouter({
    routeTree: tree,
    history: createMemoryHistory({ initialEntries: [`/minions/${minionId}`] }),
  })
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('MinionDetailPage', () => {
  it('renders grains for an online minion + filters by search', async () => {
    server.use(
      http.get('/api/minions/web-01', () =>
        HttpResponse.json({
          id: 'web-01',
          status: 'online',
          ip: '10.0.0.1',
          grains: { os: 'Ubuntu', osrelease: '22.04', kernel: 'Linux' },
        }),
      ),
    )
    const user = userEvent.setup()
    renderDetail('web-01')

    expect(await screen.findByText('os')).toBeInTheDocument()
    expect(screen.getByText('Ubuntu')).toBeInTheDocument()
    expect(screen.getByText('osrelease')).toBeInTheDocument()
    expect(screen.getByText('kernel')).toBeInTheDocument()

    await user.type(screen.getByLabelText(/filter grains by key/i), 'os')
    // 'os' and 'osrelease' match; 'kernel' does not
    await waitFor(() => {
      expect(screen.queryByText('kernel')).not.toBeInTheDocument()
    })
    expect(screen.getByText('os')).toBeInTheDocument()
    expect(screen.getByText('osrelease')).toBeInTheDocument()
  })

  it('shows the offline panel when the minion is offline', async () => {
    server.use(
      http.get('/api/minions/db-01', () =>
        HttpResponse.json({ id: 'db-01', status: 'offline', ip: null, grains: null }),
      ),
    )
    renderDetail('db-01')
    expect(await screen.findByText(/grains are only available/i)).toBeInTheDocument()
  })

  it('shows the not-found panel on 404', async () => {
    server.use(
      http.get('/api/minions/ghost', () =>
        HttpResponse.json({ detail: 'Minion not found' }, { status: 404 }),
      ),
    )
    renderDetail('ghost')
    expect(await screen.findByText(/minion not found/i)).toBeInTheDocument()
    expect(screen.getByText(/ghost/)).toBeInTheDocument()
  })
})

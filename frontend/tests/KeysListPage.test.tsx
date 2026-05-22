// frontend/tests/KeysListPage.test.tsx
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

import { KeysListPage } from '@/features/keys/keys-list-page'

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin',
      display_name: 'admin',
      must_change_pw: false,
      permissions: [
        { verb: 'view', resource_glob: 'key:*' },
        { verb: 'accept', resource_glob: 'key:*' },
        { verb: 'reject', resource_glob: 'key:*' },
        { verb: 'delete', resource_glob: 'key:*' },
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
    component: () => <KeysListPage />,
  })
  const router = createRouter({ routeTree: rootRoute.addChildren([homeRoute]) })
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('KeysListPage', () => {
  it('renders keys grouped by status', async () => {
    server.use(
      http.get('/api/keys', () =>
        HttpResponse.json({
          total: 3,
          keys: [
            { id: 'web-01', status: 'accepted' },
            { id: 'pending-host', status: 'pending' },
            { id: 'bad-host', status: 'rejected' },
          ],
        }),
      ),
    )
    renderInRouter()
    expect(await screen.findByText('web-01')).toBeInTheDocument()
    expect(screen.getByText('pending-host')).toBeInTheDocument()
    expect(screen.getByText('bad-host')).toBeInTheDocument()
    expect(screen.getByText('accepted')).toBeInTheDocument()
    expect(screen.getByText('pending')).toBeInTheDocument()
    expect(screen.getByText('rejected')).toBeInTheDocument()
  })

  it('shows state-specific actions in the row menu', async () => {
    server.use(
      http.get('/api/keys', () =>
        HttpResponse.json({
          total: 1,
          keys: [{ id: 'pending-host', status: 'pending' }],
        }),
      ),
    )
    const user = userEvent.setup()
    renderInRouter()
    await user.click(await screen.findByRole('button', { name: /actions for pending-host/i }))
    expect(await screen.findByText('Accept')).toBeInTheDocument()
    expect(screen.getByText('Reject')).toBeInTheDocument()
    expect(screen.getByText('Delete')).toBeInTheDocument()
  })

  it('shows Forbidden on 403', async () => {
    server.use(
      http.get('/api/keys', () => HttpResponse.json({ detail: 'Forbidden' }, { status: 403 })),
    )
    renderInRouter()
    expect(await screen.findByText(/don'?t have permission/i)).toBeInTheDocument()
  })
})

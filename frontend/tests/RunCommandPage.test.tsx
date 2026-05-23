// frontend/tests/RunCommandPage.test.tsx
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

import { RunCommandPage } from '@/features/run/run-command-page'

let lastBody: unknown = null
const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin',
      display_name: 'admin',
      must_change_pw: false,
      permissions: [{ verb: 'execute', resource_glob: 'salt:*' }],
    }),
  ),
  http.post('/api/run', async ({ request }) => {
    lastBody = await request.json()
    return HttpResponse.json({ jid: '20260123120000000000', minions: ['web-01'] }, { status: 202 })
  }),
)

beforeAll(() => server.listen())
afterEach(() => {
  server.resetHandlers()
  lastBody = null
})
afterAll(() => server.close())

function renderInRouter() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const rootRoute = createRootRoute({ component: Outlet })
  const homeRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    component: () => <RunCommandPage />,
  })
  const jobDetailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/jobs/$jid',
    component: () => <div>jobs-detail-stub</div>,
  })
  const router = createRouter({
    routeTree: rootRoute.addChildren([homeRoute, jobDetailRoute]),
    history: createMemoryHistory({ initialEntries: ['/'] }),
  })
  return { router, ...render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  ) }
}

describe('RunCommandPage', () => {
  it('submits target/fun/args/kwargs and navigates on success', async () => {
    const user = userEvent.setup()
    const { router } = renderInRouter()
    const targetInput = await screen.findByLabelText(/^target$/i)
    await user.clear(targetInput)
    await user.type(targetInput, 'web-*')
    await user.type(screen.getByLabelText(/^function$/i), 'test.ping')
    await user.type(screen.getByLabelText(/^arguments/i), 'a1\nb2')
    await user.type(screen.getByLabelText(/^keyword arguments/i), 'k1=v1')
    await user.click(screen.getByRole('button', { name: /^run$/i }))

    await waitFor(() => {
      expect(lastBody).toMatchObject({
        target: 'web-*',
        fun: 'test.ping',
        args: ['a1', 'b2'],
        kwargs: { k1: 'v1' },
      })
    })
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/jobs/20260123120000000000')
    })
  })

  it('shows a kwargs-format error before submitting', async () => {
    const user = userEvent.setup()
    renderInRouter()
    await user.type(await screen.findByLabelText(/^function$/i), 'test.ping')
    await user.type(screen.getByLabelText(/^keyword arguments/i), 'no_equals_sign')
    await user.click(screen.getByRole('button', { name: /^run$/i }))
    expect(await screen.findByText(/Invalid kwarg line/)).toBeInTheDocument()
    expect(lastBody).toBeNull()
  })

  it('shows a Forbidden message on 403', async () => {
    server.use(
      http.post('/api/run', () => HttpResponse.json({ detail: 'forbidden' }, { status: 403 })),
    )
    const user = userEvent.setup()
    renderInRouter()
    await user.type(await screen.findByLabelText(/^function$/i), 'test.ping')
    await user.click(screen.getByRole('button', { name: /^run$/i }))
    expect(await screen.findByText(/don.t have permission/i)).toBeInTheDocument()
  })

  it('shows a 422 detail on bad fun', async () => {
    server.use(
      http.post('/api/run', () =>
        HttpResponse.json({ detail: 'fun must be of the form module.function' }, { status: 422 }),
      ),
    )
    const user = userEvent.setup()
    renderInRouter()
    await user.type(await screen.findByLabelText(/^function$/i), 'nodot')
    await user.click(screen.getByRole('button', { name: /^run$/i }))
    expect(await screen.findByText(/module\.function/i)).toBeInTheDocument()
  })
})

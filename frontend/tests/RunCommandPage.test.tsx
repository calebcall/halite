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

function renderWithSearch(searchString: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const rootRoute = createRootRoute({ component: Outlet })
  const appRoute = createRoute({
    getParentRoute: () => rootRoute,
    id: 'app',
    component: Outlet,
  })
  const runRoute = createRoute({
    getParentRoute: () => appRoute,
    path: '/run',
    validateSearch: (s: Record<string, unknown>) => ({
      target: typeof s.target === 'string' ? s.target : undefined,
      target_type: typeof s.target_type === 'string' ? s.target_type : undefined,
      fun: typeof s.fun === 'string' ? s.fun : undefined,
      args: typeof s.args === 'string' ? s.args : undefined,
      kwargs: typeof s.kwargs === 'string' ? s.kwargs : undefined,
    }),
    component: () => <RunCommandPage />,
  })
  const jobDetailRoute = createRoute({
    getParentRoute: () => appRoute,
    path: '/jobs/$jid',
    component: () => <div>jobs-detail-stub</div>,
  })
  const router = createRouter({
    routeTree: rootRoute.addChildren([appRoute.addChildren([runRoute, jobDetailRoute])]),
    history: createMemoryHistory({ initialEntries: [`/run${searchString}`] }),
  })
  return { router, ...render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  ) }
}

function renderInRouter() {
  return renderWithSearch('')
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

  it('prefills the form from search params', async () => {
    renderWithSearch('?target=web-01&target_type=list&fun=cmd.run&args=%22%5B%5C%22ls+%2Ftmp%5C%22%5D%22&kwargs=%22%7B%5C%22shell%5C%22%3A%5C%22%2Fbin%2Fbash%5C%22%7D%22')
    expect(((await screen.findByLabelText(/^target$/i)) as HTMLInputElement).value).toBe('web-01')
    expect((screen.getByLabelText(/^function$/i) as HTMLInputElement).value).toBe('cmd.run')
    expect((screen.getByLabelText(/^arguments/i) as HTMLTextAreaElement).value).toBe('ls /tmp')
    expect((screen.getByLabelText(/^keyword arguments/i) as HTMLTextAreaElement).value).toBe('shell=/bin/bash')
  })
})

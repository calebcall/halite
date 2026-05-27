// frontend/tests/SetupWizard.test.tsx
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

import { SetupWizardPage } from '@/features/setup/setup-wizard-page'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function renderInRouter(handlers: Parameters<typeof server.use>) {
  server.use(...handlers)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const rootRoute = createRootRoute({ component: Outlet })
  const setupRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    component: () => <SetupWizardPage />,
  })
  // Add a home route so Navigate to='/' resolves after save
  const homeRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/home',
    component: () => <div>home</div>,
  })
  const router = createRouter({
    routeTree: rootRoute.addChildren([setupRoute, homeRoute]),
  })
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('SetupWizardPage', () => {
  it('Save & Continue is disabled until Test Connection succeeds', async () => {
    renderInRouter([
      http.post('/api/admin/settings/test-salt', () =>
        HttpResponse.json({ ok: true, detail: 'Logged in', minion_count: 42 }),
      ),
      http.put('/api/admin/settings/salt', () =>
        HttpResponse.json({}),
      ),
    ])
    // Wait for the router to render the page
    const save = await screen.findByRole('button', { name: /save.*continue/i })
    expect(save).toBeDisabled()

    await userEvent.type(screen.getByLabelText(/^URL$/i), 'https://salt.example/api')
    await userEvent.type(screen.getByLabelText(/^Username$/i), 'admin')
    await userEvent.type(screen.getByLabelText(/^Password$/i), 'secret')
    const test = screen.getByRole('button', { name: /test connection/i })
    await userEvent.click(test)
    await screen.findByText(/Logged in/i)
    expect(save).not.toBeDisabled()
  })

  it('Save & Continue stays disabled when Test Connection fails', async () => {
    renderInRouter([
      http.post('/api/admin/settings/test-salt', () =>
        HttpResponse.json({ ok: false, detail: 'auth failed: 401' }),
      ),
    ])
    // Wait for the router to render the page
    await screen.findByRole('button', { name: /save.*continue/i })
    await userEvent.type(screen.getByLabelText(/^URL$/i), 'https://salt.example/api')
    await userEvent.type(screen.getByLabelText(/^Username$/i), 'admin')
    await userEvent.type(screen.getByLabelText(/^Password$/i), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: /test connection/i }))
    await screen.findByText(/auth failed/i)
    expect(screen.getByRole('button', { name: /save.*continue/i })).toBeDisabled()
  })
})

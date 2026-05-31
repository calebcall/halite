// frontend/tests/SettingsPage.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
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

import { SettingsPage } from '@/features/admin/settings-page'

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin',
      display_name: 'admin',
      must_change_pw: false,
    }),
  ),
)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

const fullySetSettings = {
  salt: {
    url: 'https://salt-master.example/api',
    username: 'admin',
    password_set: true,
    verify: true,
    eauth: 'pam',
  },
  pollers: {
    inventory_refresh_minutes: 0,
    inventory_refresh_initial_delay_s: 30,
    fleet_poll_interval_seconds: 0,
    minion_state_keys_interval_seconds: 300,
    minion_state_presence_interval_seconds: 60,
    minion_state_grains_interval_seconds: 300,
    minion_state_initial_delay_seconds: 10,
  },
  logging: { log_format: 'json' as const },
  widget: {
    widget_hide_dispatch: true,
    widget_hide_routine: false,
    widget_show_jobs: true,
    widget_show_keys: true,
    widget_show_minions: true,
    widget_event_count: 6,
    widget_heartbeat_minutes: 60,
  },
  updated_at: new Date().toISOString(),
}

function renderInRouter(handlers: Parameters<typeof server.use>) {
  server.use(...handlers)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const rootRoute = createRootRoute({ component: Outlet })
  const settingsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    component: () => <SettingsPage />,
  })
  const router = createRouter({ routeTree: rootRoute.addChildren([settingsRoute]) })
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('SettingsPage', () => {
  it('renders three sections with seeded values', async () => {
    renderInRouter([
      http.get('/api/admin/settings', () => HttpResponse.json(fullySetSettings)),
    ])
    expect(await screen.findByText(/Salt API/i)).toBeInTheDocument()
    expect(screen.getByText(/^Pollers$/i)).toBeInTheDocument()
    expect(screen.getByText(/^Logging$/i)).toBeInTheDocument()
    const urlInput = await screen.findByDisplayValue(/salt-master.example/i)
    expect(urlInput).toBeInTheDocument()
  })

  it('password field shows "(set)" placeholder when password_set is true', async () => {
    renderInRouter([
      http.get('/api/admin/settings', () => HttpResponse.json(fullySetSettings)),
    ])
    const pwInput = await screen.findByPlaceholderText(/set/i)
    expect(pwInput).toBeInTheDocument()
  })

  it('PUT /api/admin/settings/salt omits password when input is blank', async () => {
    let receivedBody: Record<string, unknown> | null = null
    renderInRouter([
      http.get('/api/admin/settings', () => HttpResponse.json(fullySetSettings)),
      http.put('/api/admin/settings/salt', async ({ request }) => {
        receivedBody = await request.json() as Record<string, unknown>
        return HttpResponse.json(fullySetSettings)
      }),
    ])
    await screen.findByDisplayValue(/salt-master.example/i)
    const saveButtons = await screen.findAllByRole('button', { name: /^Save$/i })
    await userEvent.click(saveButtons[0])
    await waitFor(() => expect(receivedBody).not.toBeNull())
    expect(receivedBody!.password ?? null).toBeNull()
  })

  it('renders the Activity widget section seeded from initial.widget', async () => {
    renderInRouter([
      http.get('/api/admin/settings', () => HttpResponse.json(fullySetSettings)),
    ])
    expect(await screen.findByText(/^Activity widget$/i)).toBeInTheDocument()
    const eventCount = document.getElementById('widget-event-count') as HTMLInputElement
    const heartbeat = document.getElementById('widget-heartbeat-minutes') as HTMLInputElement
    expect(eventCount.value).toBe('6')
    expect(heartbeat.value).toBe('60')
  })

  it('PUT /api/admin/settings/widget submits the widget patch', async () => {
    let receivedBody: Record<string, unknown> | null = null
    renderInRouter([
      http.get('/api/admin/settings', () => HttpResponse.json(fullySetSettings)),
      http.put('/api/admin/settings/widget', async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(fullySetSettings.widget)
      }),
    ])
    await screen.findByText(/^Activity widget$/i)
    const saveButtons = await screen.findAllByRole('button', { name: /^Save$/i })
    // Sections render in order: Salt, Pollers, Activity widget, Logging.
    await userEvent.click(saveButtons[2])
    await waitFor(() => expect(receivedBody).not.toBeNull())
    expect(receivedBody!.widget_event_count).toBe(6)
    expect(receivedBody!.widget_hide_dispatch).toBe(true)
  })

  it('Test Connection button calls /api/admin/settings/test-salt', async () => {
    let testCalled = false
    renderInRouter([
      http.get('/api/admin/settings', () => HttpResponse.json(fullySetSettings)),
      http.post('/api/admin/settings/test-salt', async () => {
        testCalled = true
        return HttpResponse.json({ ok: true, detail: 'Logged in', minion_count: 42 })
      }),
    ])
    const pwInput = await screen.findByPlaceholderText(/set/i)
    await userEvent.type(pwInput, 'secret')
    const testBtn = screen.getByRole('button', { name: /test connection/i })
    await userEvent.click(testBtn)
    await waitFor(() => expect(testCalled).toBe(true))
    expect(await screen.findByText(/Logged in \(42 minions\)/i)).toBeInTheDocument()
  })
})

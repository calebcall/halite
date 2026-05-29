// frontend/tests/ActivityPage.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { ActivityPage } from '@/features/activity/activity-page'

// Shim EventSource in case any code path touches it
globalThis.EventSource = class {
  close() {}
} as unknown as typeof EventSource

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin',
      display_name: 'admin',
      must_change_pw: false,
      permissions: [{ verb: 'view', resource_glob: 'job:*' }],
    }),
  ),
  http.get('/api/activity', () =>
    HttpResponse.json({
      total: 1,
      events: [
        {
          id: 1,
          ts: '2026-05-29T12:00:00Z',
          category: 'job',
          event_type: 'job.ret',
          minion_id: 'web-01',
          jid: '20260529120000000000',
          fun: 'test.ping',
          success: true,
          summary: 'test.ping returned on web-01',
        },
      ],
    }),
  ),
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ActivityPage />
    </QueryClientProvider>,
  )
}

describe('ActivityPage', () => {
  it('renders a job event with its summary', async () => {
    renderPage()
    expect(await screen.findByText('test.ping returned on web-01')).toBeInTheDocument()
  })

  it('renders the event_type and minion_id columns', async () => {
    renderPage()
    expect(await screen.findByText('job.ret')).toBeInTheDocument()
    expect(screen.getByText('web-01')).toBeInTheDocument()
  })

  it('shows no-access message when user has no view perms', async () => {
    server.use(
      http.get('/api/auth/me', () =>
        HttpResponse.json({
          username: 'restricted',
          display_name: 'restricted',
          must_change_pw: false,
          permissions: [],
        }),
      ),
    )
    renderPage()
    expect(
      await screen.findByText(/you don't have access to any activity/i),
    ).toBeInTheDocument()
  })

  it('shows error state when the activity endpoint returns 500', async () => {
    server.use(
      http.get('/api/activity', () => HttpResponse.json({ detail: 'oops' }, { status: 500 })),
    )
    renderPage()
    expect(await screen.findByText(/failed to load activity/i)).toBeInTheDocument()
  })
})

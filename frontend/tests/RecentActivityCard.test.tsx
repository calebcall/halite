// frontend/tests/RecentActivityCard.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

// RecentActivityCard renders a <Link to="/activity"> from @tanstack/react-router.
// Stub it with a plain anchor so we don't need a full router tree.
vi.mock('@tanstack/react-router', () => ({
  Link: ({
    children,
    to,
    className,
  }: {
    children?: React.ReactNode
    to?: string
    className?: string
  }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}))

import { RecentActivityCard } from '@/features/activity/recent-activity-card'

// Shim EventSource so any transitive import doesn't crash jsdom
globalThis.EventSource = class {
  close() {}
} as unknown as typeof EventSource

const recentEvent = {
  id: 42,
  ts: '2026-05-29T12:00:00Z',
  category: 'job',
  event_type: 'job.ret',
  minion_id: 'web-01',
  jid: '20260529120000000000',
  fun: 'state.highstate',
  success: false,
  changed: false,
  summary: 'state.highstate failed on web-01',
}

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin',
      display_name: 'Admin',
      must_change_pw: false,
      permissions: [{ verb: 'view', resource_glob: 'job:*' }],
    }),
  ),
  // The card calls /api/activity twice: heartbeat (since_minutes=60, limit=1)
  // and notable recent (hide_routine=true, limit=6). Branch on since_minutes:
  // the heartbeat only reads `total`, the list reads `events`.
  http.get('/api/activity', ({ request }) => {
    const url = new URL(request.url)
    if (url.searchParams.get('since_minutes') === '60') {
      return HttpResponse.json({ total: 142, events: [] })
    }
    return HttpResponse.json({ total: 1, events: [recentEvent] })
  }),
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <RecentActivityCard />
    </QueryClientProvider>,
  )
}

describe('RecentActivityCard', () => {
  it('renders the heartbeat count for the last hour', async () => {
    renderCard()
    expect(await screen.findByText('142')).toBeInTheDocument()
    expect(screen.getByText(/events · last hour/i)).toBeInTheDocument()
  })

  it('renders a recent notable event', async () => {
    renderCard()
    expect(await screen.findByText('web-01')).toBeInTheDocument()
    expect(screen.getByText('state.highstate')).toBeInTheDocument()
  })

  it('renders a "View all" link pointing to /activity', async () => {
    renderCard()
    await screen.findByText('web-01')
    const link = screen.getByRole('link', { name: /view all/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/activity')
  })

  it('shows "No notable activity" when the recent feed is empty', async () => {
    server.use(
      http.get('/api/activity', ({ request }) => {
        const url = new URL(request.url)
        if (url.searchParams.get('since_minutes') === '60') {
          return HttpResponse.json({ total: 0, events: [] })
        }
        return HttpResponse.json({ total: 0, events: [] })
      }),
    )
    renderCard()
    expect(await screen.findByText(/no notable activity/i)).toBeInTheDocument()
  })
})

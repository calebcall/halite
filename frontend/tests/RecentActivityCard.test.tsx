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

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin',
      display_name: 'Admin',
      must_change_pw: false,
      permissions: [{ verb: 'view', resource_glob: 'job:*' }],
    }),
  ),
  http.get('/api/activity', () =>
    HttpResponse.json({
      total: 1,
      events: [
        {
          id: 42,
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

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <RecentActivityCard />
    </QueryClientProvider>,
  )
}

describe('RecentActivityCard', () => {
  it('renders an event summary from the activity feed', async () => {
    renderCard()
    expect(await screen.findByText('test.ping returned on web-01')).toBeInTheDocument()
  })

  it('renders a "View all" link pointing to /activity', async () => {
    renderCard()
    // wait for data to load so component is stable
    await screen.findByText('test.ping returned on web-01')
    const link = screen.getByRole('link', { name: /view all/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/activity')
  })

  it('shows "No activity yet" when the feed is empty', async () => {
    server.use(
      http.get('/api/activity', () =>
        HttpResponse.json({ total: 0, events: [] }),
      ),
    )
    renderCard()
    expect(await screen.findByText(/no activity yet/i)).toBeInTheDocument()
  })

  it('shows the event category label', async () => {
    renderCard()
    expect(await screen.findByText('job')).toBeInTheDocument()
  })
})

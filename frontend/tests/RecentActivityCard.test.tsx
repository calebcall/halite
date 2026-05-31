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
  initiator: 'scheduler',
  target: null,
  duration_ms: 4200,
  summary: 'state.highstate failed on web-01',
}

// A job.new dispatch event — should be excluded when hide_dispatch=true
const dispatchEvent = {
  id: 99,
  ts: '2026-05-29T12:01:00Z',
  category: 'job',
  event_type: 'job.new',
  minion_id: null,
  jid: '20260529120100000000',
  fun: 'state.apply',
  success: null,
  changed: null,
  initiator: 'user',
  target: 'web/*',
  duration_ms: null,
  summary: 'Dispatched state.apply → web/*',
}

// Default widget config (mirrors the backend WidgetConfigOut defaults).
const defaultWidgetConfig = {
  widget_hide_dispatch: true,
  widget_hide_routine: false,
  widget_show_jobs: true,
  widget_show_keys: true,
  widget_show_minions: true,
  widget_event_count: 6,
  widget_heartbeat_minutes: 60,
}

// Tracks params seen on the recent-list query
let lastHideDispatch: string | null = null
let lastLimit: string | null = null
let lastCategories: string | null = null
let lastSinceMinutes: string | null = null

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin',
      display_name: 'Admin',
      must_change_pw: false,
      permissions: [{ verb: 'view', resource_glob: 'job:*' }],
    }),
  ),
  http.get('/api/activity/widget-config', () => HttpResponse.json(defaultWidgetConfig)),
  // The card calls /api/activity twice:
  //   heartbeat: since_minutes=<window>, limit=1  → reads `total` only
  //   recent list: hide_dispatch, limit, categories → reads `events`
  // Branch on since_minutes to distinguish the two requests.
  http.get('/api/activity', ({ request }) => {
    const url = new URL(request.url)
    if (url.searchParams.get('since_minutes')) {
      lastSinceMinutes = url.searchParams.get('since_minutes')
      return HttpResponse.json({ total: 142, events: [] })
    }
    lastHideDispatch = url.searchParams.get('hide_dispatch')
    lastLimit = url.searchParams.get('limit')
    lastCategories = url.searchParams.get('categories')
    // hide_dispatch=true → return only non-dispatch events (simulate server filtering)
    // hide_dispatch not set → include the job.new dispatch event too
    const hideDispatch = lastHideDispatch === 'true'
    if (hideDispatch) {
      return HttpResponse.json({ total: 1, events: [recentEvent] })
    }
    return HttpResponse.json({ total: 2, events: [dispatchEvent, recentEvent] })
  }),
)

beforeAll(() => server.listen())
afterEach(() => {
  server.resetHandlers()
  lastHideDispatch = null
  lastLimit = null
  lastCategories = null
  lastSinceMinutes = null
})
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
    expect(screen.getByText(/events · last hour/i)).toBeInTheDocument() // default config: 60 min → "last hour"
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

  it('applies hide_dispatch from the widget config on the recent-list request', async () => {
    renderCard()
    await screen.findByText('web-01')
    expect(lastHideDispatch).toBe('true')
  })

  it('applies widget_event_count from config as the recent-list limit', async () => {
    renderCard()
    await screen.findByText('web-01')
    // Default config event count is 6.
    expect(lastLimit).toBe('6')
  })

  it('requests a non-default limit when the config specifies one', async () => {
    server.use(
      http.get('/api/activity/widget-config', () =>
        HttpResponse.json({ ...defaultWidgetConfig, widget_event_count: 12 }),
      ),
    )
    renderCard()
    await screen.findByText('web-01')
    expect(lastLimit).toBe('12')
  })

  it('omits the categories param when all three categories are enabled', async () => {
    renderCard()
    await screen.findByText('web-01')
    expect(lastCategories).toBeNull()
  })

  it('sends a categories CSV when some categories are disabled', async () => {
    server.use(
      http.get('/api/activity/widget-config', () =>
        HttpResponse.json({ ...defaultWidgetConfig, widget_show_minions: false }),
      ),
    )
    renderCard()
    await screen.findByText('web-01')
    expect(lastCategories).toBe('job,key')
  })

  it('uses the configured heartbeat window for the heartbeat query', async () => {
    server.use(
      http.get('/api/activity/widget-config', () =>
        HttpResponse.json({ ...defaultWidgetConfig, widget_heartbeat_minutes: 120 }),
      ),
    )
    renderCard()
    await screen.findByText('142')
    expect(lastSinceMinutes).toBe('120')
  })

  it('does not render job.new dispatch events when hide_dispatch=true', async () => {
    renderCard()
    // Wait for the non-dispatch event to appear, confirming the list rendered
    await screen.findByText('web-01')
    // The dispatch event's function name must not appear — the widget excludes dispatches
    expect(screen.queryByText('web/*')).not.toBeInTheDocument()
  })

  it('shows "No notable activity" when the recent feed is empty', async () => {
    server.use(
      http.get('/api/activity', () => HttpResponse.json({ total: 0, events: [] })),
    )
    renderCard()
    expect(await screen.findByText(/no notable activity/i)).toBeInTheDocument()
  })
})

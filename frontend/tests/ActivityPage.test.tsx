// frontend/tests/ActivityPage.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { ActivityPage } from '@/features/activity/activity-page'

// Shim EventSource in case any code path touches it
globalThis.EventSource = class {
  close() {}
} as unknown as typeof EventSource

// Captures the hide_routine query param of the most recent /api/activity call.
let lastHideRoutine: string | null = null

const failedEvent = {
  id: 1,
  ts: '2026-05-29T12:00:00Z',
  category: 'job',
  event_type: 'job.ret',
  minion_id: 'web-01',
  jid: '20260529120000000000',
  fun: 'state.highstate',
  success: false,
  changed: false,
  initiator: null,
  target: null,
  duration_ms: 4200,
  summary: 'state.highstate failed on web-01',
}

const changedEvent = {
  id: 2,
  ts: '2026-05-29T12:01:00Z',
  category: 'job',
  event_type: 'job.ret',
  minion_id: 'db-02',
  jid: '20260529120100000000',
  fun: 'state.highstate',
  success: true,
  changed: true,
  initiator: null,
  target: null,
  duration_ms: null,
  summary: 'state.highstate applied changes on db-02',
}

const okEvent = {
  id: 3,
  ts: '2026-05-29T12:02:00Z',
  category: 'job',
  event_type: 'job.ret',
  minion_id: 'web-03',
  jid: '20260529120200000000',
  fun: 'state.highstate',
  success: true,
  changed: false,
  initiator: null,
  target: null,
  duration_ms: null,
  summary: 'state.highstate returned on web-03',
}

// A job.new dispatch: no minion_id, but a target glob and an initiator.
const dispatchEvent = {
  id: 4,
  ts: '2026-05-29T12:03:00Z',
  category: 'job',
  event_type: 'job.new',
  minion_id: null,
  jid: '20260529120300000000',
  fun: 'test.ping',
  success: null,
  changed: null,
  initiator: 'admin',
  target: 'web/*',
  duration_ms: null,
  summary: 'test.ping dispatched to web/*',
}

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin',
      display_name: 'admin',
      must_change_pw: false,
      permissions: [{ verb: 'view', resource_glob: 'job:*' }],
    }),
  ),
  http.get('/api/activity', ({ request }) => {
    const url = new URL(request.url)
    lastHideRoutine = url.searchParams.get('hide_routine')
    const hideRoutine = lastHideRoutine === 'true'
    const events = hideRoutine
      ? [failedEvent, changedEvent, dispatchEvent]
      : [failedEvent, changedEvent, dispatchEvent, okEvent]
    return HttpResponse.json({ total: events.length, events })
  }),
)

beforeAll(() => server.listen())
afterEach(() => {
  server.resetHandlers()
  lastHideRoutine = null
})
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
  it('defaults to hide_routine=true and renders Failed and Changes rows', async () => {
    renderPage()
    expect(await screen.findByText('web-01')).toBeInTheDocument()
    expect(screen.getByText('Failed')).toBeInTheDocument()
    expect(screen.getByText('Changes')).toBeInTheDocument()
    // routine OK row should not be present by default
    expect(screen.queryByText('OK')).not.toBeInTheDocument()
    expect(lastHideRoutine).toBe('true')
  })

  it('shows the target as the subject for a job.new dispatch and the initiator', async () => {
    renderPage()
    // job.new has no minion_id — the subject should be the target glob,
    // never the literal "fleet".
    expect(await screen.findByText('web/*')).toBeInTheDocument()
    expect(screen.queryByText('fleet')).not.toBeInTheDocument()
    expect(screen.getByText('by admin')).toBeInTheDocument()
    expect(screen.getByText('Dispatched')).toBeInTheDocument()
  })

  it('renders the formatted duration for a job.ret with duration_ms', async () => {
    renderPage()
    // failedEvent has duration_ms 4200 → "4.2s"
    expect(await screen.findByText('4.2s')).toBeInTheDocument()
  })

  it('toggling "Show routine successes" sends hide_routine=false and shows OK rows', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('web-01')

    await user.click(screen.getByRole('switch', { name: /show routine successes/i }))

    // The routine success row renders with the "OK" success badge.
    expect(await screen.findByText('OK')).toBeInTheDocument()
    expect(lastHideRoutine).toBe('false')
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

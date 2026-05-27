import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

// MinionRunPanel renders a <Link> from @tanstack/react-router which requires a
// RouterProvider context. Since this test only checks the summary line, mock it
// to a plain anchor to avoid setting up a full router.
vi.mock('@tanstack/react-router', () => ({
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
}))

import { MinionRunPanel } from '@/features/fleet/minion-run-panel'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function withQuery(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
}

const minionFixture = {
  change_count: 0,
  completed_at: new Date().toISOString(),
  duration_ms: 0,
  fail_count: 1,
  jid: 'J1',
  minion_id: 'web-1',
  pass_count: 0,
  run_id: '11111111-1111-1111-1111-111111111111',
  status: 'fail' as const,
  total_count: 1,
}

describe('MinionRunPanel', () => {
  it('renders summary line from fetched run', async () => {
    server.use(
      http.get('/api/fleet/runs/:id', () =>
        HttpResponse.json({
          blocked: false,
          change_count: 0,
          completed_at: minionFixture.completed_at,
          duration_ms: 10,
          fail_count: 1,
          fun: 'state.apply',
          id: minionFixture.run_id,
          jid: 'J1',
          minion_id: 'web-1',
          pass_count: 0,
          raw_result: {
            'service_|-redis_run_|-redis_|-running': {
              __run_num__: 1,
              changes: {},
              comment: 'boom',
              duration: 10,
              result: false,
            },
          },
          total_count: 1,
        }),
      ),
    )
    render(
      withQuery(
        <MinionRunPanel minion={minionFixture} open={true} onOpenChange={() => {}} />,
      ),
    )
    expect(await screen.findByText(/1 states/i)).toBeInTheDocument()
    expect(await screen.findByText(/1 failed/i)).toBeInTheDocument()
  })
})

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { FleetHeatmap } from '@/features/fleet/fleet-heatmap'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function withQuery(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
}

function mockBody(minions: Array<{ minion_id: string; status: string; pass_count?: number; fail_count?: number; change_count?: number; total_count?: number; jid?: string; run_id?: string; completed_at?: string; duration_ms?: number }>) {
  return {
    total_minions: minions.length,
    minions: minions.map((m) => ({
      change_count: m.change_count ?? 0,
      completed_at: m.completed_at ?? new Date().toISOString(),
      duration_ms: m.duration_ms ?? 0,
      fail_count: m.fail_count ?? 0,
      jid: m.jid ?? 'J1',
      minion_id: m.minion_id,
      pass_count: m.pass_count ?? 0,
      run_id: m.run_id ?? '00000000-0000-0000-0000-000000000000',
      status: m.status,
      total_count: m.total_count ?? 0,
    })),
  }
}

describe('FleetHeatmap', () => {
  it('renders one tile per minion', async () => {
    server.use(
      http.get('/api/fleet/health', () =>
        HttpResponse.json(mockBody([
          { minion_id: 'web-1', status: 'pass' },
          { minion_id: 'web-2', status: 'fail' },
          { minion_id: 'db-1', status: 'changed' },
        ])),
      ),
    )
    render(withQuery(<FleetHeatmap onTileClick={() => {}} />))
    expect(await screen.findByRole('button', { name: /web-1 pass/i })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /web-2 fail/i })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /db-1 changed/i })).toBeInTheDocument()
  })

  it('filter narrows the visible tiles', async () => {
    server.use(
      http.get('/api/fleet/health', () =>
        HttpResponse.json(mockBody([
          { minion_id: 'web-1', status: 'pass' },
          { minion_id: 'db-1', status: 'pass' },
        ])),
      ),
    )
    render(withQuery(<FleetHeatmap onTileClick={() => {}} />))
    await screen.findByRole('button', { name: /web-1 pass/i })
    const input = screen.getByLabelText('Filter minions')
    await userEvent.type(input, 'db')
    expect(screen.queryByRole('button', { name: /web-1 pass/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /db-1 pass/i })).toBeInTheDocument()
  })

  it('fires onTileClick with the minion', async () => {
    const cb = vi.fn()
    server.use(
      http.get('/api/fleet/health', () =>
        HttpResponse.json(mockBody([{ minion_id: 'web-1', status: 'pass' }])),
      ),
    )
    render(withQuery(<FleetHeatmap onTileClick={cb} />))
    const tile = await screen.findByRole('button', { name: /web-1 pass/i })
    await userEvent.click(tile)
    expect(cb).toHaveBeenCalledTimes(1)
    expect(cb.mock.calls[0][0]).toMatchObject({ minion_id: 'web-1', status: 'pass' })
  })
})

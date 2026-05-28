// frontend/tests/MinionDetailPage.test.tsx
// P28 T9: smoke tests for the enriched minion detail page sub-components.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

// MinionRunsTable transitively renders MinionRunPanel, which imports
// Link from @tanstack/react-router. Stub it with a plain anchor so we
// don't need a full router tree for these smoke tests.
vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, ...rest }: { children?: React.ReactNode; [k: string]: unknown }) => (
    <a {...rest}>{children}</a>
  ),
}))

import { MinionGrainExplorer } from '@/features/minions/minion-grain-explorer'
import { MinionRunsTable } from '@/features/minions/minion-runs-table'
import { MinionStatusHeader } from '@/features/minions/minion-status-header'

import type { components } from '@/shared/api/types.gen'

type MinionDetail = components['schemas']['MinionDetail']
type RunSummary = components['schemas']['MinionRunSummary']
type RunsOut = components['schemas']['MinionRunsOut']

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function withQuery(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
}

function makeRun(over: Partial<RunSummary> = {}): RunSummary {
  return {
    blocked: false,
    change_count: 0,
    completed_at: '2026-05-28T12:00:00Z',
    duration_ms: 1234,
    fail_count: 0,
    fun: 'state.apply',
    id: '11111111-1111-1111-1111-111111111111',
    jid: 'J1',
    pass_count: 5,
    status: 'healthy',
    total_count: 5,
    ...over,
  }
}

describe('MinionStatusHeader', () => {
  it('renders status header with grain-derived facts', () => {
    const minion: MinionDetail = {
      grains: {
        kernel: 'Linux',
        kernelrelease: '5.15',
        mem_total: 8192,
        num_cpus: 4,
        os: 'Ubuntu',
        osrelease: '22.04',
      },
      id: 'web-01',
      ip: '10.0.0.1',
      status: 'online',
    }
    render(<MinionStatusHeader minion={minion} />)
    expect(screen.getByText('Ubuntu 22.04')).toBeInTheDocument()
    expect(screen.getByText('web-01')).toBeInTheDocument()
    expect(screen.getByText('10.0.0.1')).toBeInTheDocument()
  })
})

describe('MinionRunsTable', () => {
  it('renders rows for each run returned by the API', async () => {
    const payload: RunsOut = {
      minion_id: 'web-01',
      runs: [
        makeRun({ id: 'r1', jid: 'J1', status: 'healthy' }),
        makeRun({
          fail_count: 2,
          id: 'r2',
          jid: 'J2',
          pass_count: 3,
          status: 'unhealthy',
          total_count: 5,
        }),
      ],
      total: 2,
    }
    server.use(
      http.get('/api/minions/web-01/runs', () => HttpResponse.json(payload)),
    )
    render(withQuery(<MinionRunsTable minionId="web-01" />))

    expect(await screen.findByText('healthy')).toBeInTheDocument()
    expect(screen.getByText('unhealthy')).toBeInTheDocument()
    // Two rows in the tbody (one per run).
    const table = screen.getByRole('table')
    const tbody = table.querySelector('tbody')
    expect(tbody?.querySelectorAll('tr').length).toBe(2)
  })

  it('shows the empty-state message when no runs have been ingested', async () => {
    const payload: RunsOut = { minion_id: 'x', runs: [], total: 0 }
    server.use(
      http.get('/api/minions/x/runs', () => HttpResponse.json(payload)),
    )
    render(withQuery(<MinionRunsTable minionId="x" />))

    expect(
      await screen.findByText(/no highstate runs ingested/i),
    ).toBeInTheDocument()
  })
})

describe('MinionGrainExplorer', () => {
  it('filter input narrows the visible list to matching keys', async () => {
    const grains = {
      kernel: 'Linux',
      mem_total: 8192,
      num_cpus: 4,
      os: 'Ubuntu',
      osrelease: '22.04',
    }
    render(<MinionGrainExplorer grains={grains} />)

    // All five keys visible initially.
    expect(screen.getByText('os')).toBeInTheDocument()
    expect(screen.getByText('osrelease')).toBeInTheDocument()
    expect(screen.getByText('kernel')).toBeInTheDocument()
    expect(screen.getByText('num_cpus')).toBeInTheDocument()
    expect(screen.getByText('mem_total')).toBeInTheDocument()

    const filter = screen.getByLabelText(/filter grains/i)
    await userEvent.type(filter, 'os')

    // 'os', 'osrelease', and 'mem_total' (value contains '8192' — no 'os')
    // After typing 'os', only keys/values matching 'os' remain.
    // 'os' (key) matches, 'osrelease' (key) matches, 'kernel' (no), 'num_cpus' (no), 'mem_total' (no).
    expect(screen.getByText('os')).toBeInTheDocument()
    expect(screen.getByText('osrelease')).toBeInTheDocument()
    expect(screen.queryByText('kernel')).not.toBeInTheDocument()
    expect(screen.queryByText('num_cpus')).not.toBeInTheDocument()
    expect(screen.queryByText('mem_total')).not.toBeInTheDocument()
  })
})

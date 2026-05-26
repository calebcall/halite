// frontend/tests/JobDetailPage.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory,
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

import { JobDetailPage } from '@/features/jobs/job-detail-page'

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin',
      display_name: 'admin',
      must_change_pw: false,
      permissions: [
        { verb: 'view', resource_glob: 'job:*' },
        { verb: 'execute', resource_glob: 'salt:*' },
        { verb: 'kill', resource_glob: 'job:*' },
      ],
    }),
  ),
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function renderAt(jid: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const rootRoute = createRootRoute({ component: Outlet })
  const appRoute = createRoute({
    getParentRoute: () => rootRoute,
    id: 'app',
    component: Outlet,
  })
  const jobsRoute = createRoute({
    getParentRoute: () => appRoute,
    path: '/jobs',
    component: () => <div>jobs-list-stub</div>,
  })
  const detailRoute = createRoute({
    getParentRoute: () => appRoute,
    path: '/jobs/$jid',
    component: () => <JobDetailPage />,
  })
  const router = createRouter({
    routeTree: rootRoute.addChildren([appRoute.addChildren([jobsRoute, detailRoute])]),
    history: createMemoryHistory({ initialEntries: [`/jobs/${jid}`] }),
  })
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('JobDetailPage', () => {
  it('renders job metadata + per-minion results', async () => {
    server.use(
      http.get('/api/jobs/:jid', () =>
        HttpResponse.json({
          jid: '20251019120000123456',
          function: 'state.apply',
          arguments: ['mystate'],
          kwargs: { pillar: { foo: 'bar' } },
          target: '*',
          target_type: 'glob',
          user: 'halite-service',
          start_time: '2025-10-19T12:00:00',
          minions: ['web-01', 'web-02'],
          results: [
            { minion: 'web-01', success: true, retcode: 0, return_value: true },
            { minion: 'web-02', success: false, retcode: 1, return_value: 'perm denied' },
          ],
        }),
      ),
    )
    renderAt('20251019120000123456')
    expect(await screen.findByText('20251019120000123456')).toBeInTheDocument()
    expect(screen.getByText(/state\.apply on \*/i)).toBeInTheDocument()
    expect(screen.getByText('web-01')).toBeInTheDocument()
    expect(screen.getByText('web-02')).toBeInTheDocument()
    expect(screen.getByText('success')).toBeInTheDocument()
    expect(screen.getByText('failed')).toBeInTheDocument()
    expect(screen.getByText(/Keyword arguments/i)).toBeInTheDocument()
    expect(screen.getByText(/"pillar"/)).toBeInTheDocument()
  })

  it('expands a minion result on click', async () => {
    server.use(
      http.get('/api/jobs/:jid', () =>
        HttpResponse.json({
          jid: 'j1',
          function: 'test.ping',
          arguments: [],
          kwargs: {},
          target: '*',
          target_type: 'glob',
          user: 'halite-service',
          start_time: '2025-10-19T12:00:00',
          minions: ['web-01'],
          results: [{ minion: 'web-01', success: true, retcode: 0, return_value: { ok: 1 } }],
        }),
      ),
    )
    const user = userEvent.setup()
    renderAt('j1')
    const trigger = await screen.findByRole('button', { name: /web-01/i })
    await user.click(trigger)
    expect(screen.getByText(/"ok": 1/)).toBeInTheDocument()
  })

  it('renders highstate view when return_value matches the low-state shape', async () => {
    server.use(
      http.get('/api/jobs/:jid', () =>
        HttpResponse.json({
          jid: 'j-highstate',
          function: 'state.apply',
          arguments: ['webserver'],
          kwargs: {},
          target: 'web-01',
          target_type: 'glob',
          user: 'halite-service',
          start_time: '2025-10-19T12:00:00',
          minions: ['web-01'],
          results: [{
            minion: 'web-01',
            success: true,
            retcode: 0,
            return_value: {
              'pkg_|-install_nginx_|-nginx_|-installed': {
                name: 'nginx',
                changes: { nginx: { old: '', new: '1.18.0' } },
                result: true,
                comment: 'Package nginx is installed',
                duration: 234.5,
                __run_num__: 0,
                __sls__: 'webserver',
              },
              'service_|-nginx_running_|-nginx_|-running': {
                name: 'nginx',
                changes: {},
                result: true,
                comment: 'Service is already running',
                duration: 12.3,
                __run_num__: 1,
                __sls__: 'webserver',
              },
            },
          }],
        }),
      ),
    )
    const user = userEvent.setup()
    renderAt('j-highstate')
    // Expand the minion row
    const trigger = await screen.findByRole('button', { name: /web-01/i })
    await user.click(trigger)

    // Summary line — the outer <span> has mixed content (<span>2</span> states),
    // so use a function matcher that checks the full textContent of the element.
    const summarySpan = (text: RegExp) =>
      screen.getByText((_content, element) => {
        if (!element) return false
        return element.tagName === 'SPAN' && text.test(element.textContent ?? '')
      })
    expect(summarySpan(/2 states/)).toBeInTheDocument()
    expect(summarySpan(/1 with changes/)).toBeInTheDocument()
    expect(summarySpan(/0 failed/)).toBeInTheDocument()

    // Each state row's content
    expect(screen.getByText('install_nginx')).toBeInTheDocument()
    expect(screen.getByText('nginx_running')).toBeInTheDocument()
    expect(screen.getByText('Package nginx is installed')).toBeInTheDocument()
    expect(screen.getByText('Service is already running')).toBeInTheDocument()

    // Module.fun badges
    expect(screen.getByText('pkg.installed')).toBeInTheDocument()
    expect(screen.getByText('service.running')).toBeInTheDocument()
  })

  it('shows job-level summary and failures-only filter for highstate jobs', async () => {
    const okMinion = {
      minion: 'web-01',
      success: true,
      retcode: 0,
      return_value: {
        'pkg_|-install_nginx_|-nginx_|-installed': {
          name: 'nginx',
          result: true,
          comment: 'Already installed',
          changes: {},
          __run_num__: 0,
        },
      },
    }
    const failedMinion = {
      minion: 'web-02',
      success: false,
      retcode: 1,
      return_value: {
        'pkg_|-install_nginx_|-nginx_|-installed': {
          name: 'nginx',
          result: false,
          comment: 'Package install failed',
          changes: {},
          __run_num__: 0,
        },
      },
    }
    server.use(
      http.get('/api/jobs/:jid', () =>
        HttpResponse.json({
          jid: 'j-mixed',
          function: 'state.apply',
          arguments: ['webserver'],
          kwargs: {},
          target: 'web-*',
          target_type: 'glob',
          user: 'halite-service',
          start_time: '2025-10-19T12:00:00',
          minions: ['web-01', 'web-02'],
          results: [okMinion, failedMinion],
        }),
      ),
    )
    const user = userEvent.setup()
    renderAt('j-mixed')

    // Job-level summary renders with mixed counts.
    // The summary uses nested <span>s, so we wait for the outer wrapper whose
    // textContent includes both the count and the label.
    await screen.findByText((_content, element) => {
      if (!element) return false
      return element.tagName === 'SPAN' && /2.*minion/i.test(element.textContent ?? '')
    })
    // The inner <span> contains exactly "with failures" — use getAllBy to handle
    // any ancestor span that also contains the same substring.
    expect(screen.getAllByText(/with failures/i).length).toBeGreaterThan(0)

    // Both minion rows visible initially
    expect(screen.getByRole('button', { name: /web-01/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /web-02/i })).toBeInTheDocument()

    // Toggle the Switch
    await user.click(screen.getByRole('switch', { name: /show failures only/i }))

    // web-01 (healthy) hidden; web-02 (failed) still visible
    expect(screen.queryByRole('button', { name: /web-01/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /web-02/i })).toBeInTheDocument()
  })

  it('does not show job-level summary or filter Switch for non-highstate jobs', async () => {
    server.use(
      http.get('/api/jobs/:jid', () =>
        HttpResponse.json({
          jid: 'j-plain',
          function: 'test.ping',
          arguments: [],
          kwargs: {},
          target: '*',
          target_type: 'glob',
          user: 'halite-service',
          start_time: '2025-10-19T12:00:00',
          minions: ['web-01'],
          results: [{ minion: 'web-01', success: true, retcode: 0, return_value: true }],
        }),
      ),
    )
    renderAt('j-plain')
    await screen.findByRole('button', { name: /web-01/i })
    // The highstate-specific aggregate language should NOT appear
    expect(screen.queryByText(/with failures/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/state changes/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('switch', { name: /show failures only/i })).not.toBeInTheDocument()
  })

  it('renders Run again button with encoded search params', async () => {
    server.use(
      http.get('/api/jobs/:jid', () =>
        HttpResponse.json({
          jid: '20251019120000123456',
          function: 'state.apply',
          arguments: ['mystate'],
          kwargs: { pillar: { env: 'prod' } },
          target: 'web-*',
          target_type: 'glob',
          user: 'halite-service',
          start_time: '2025-10-19T12:00:00',
          minions: ['web-01'],
          results: [{ minion: 'web-01', success: true, retcode: 0, return_value: true }],
        }),
      ),
    )
    renderAt('20251019120000123456')
    const link = await screen.findByRole('link', { name: /run again/i })
    expect(link).toBeInTheDocument()
    const href = link.getAttribute('href') || ''
    expect(href).toContain('target=')
    expect(href).toContain('fun=')
    expect(href).toContain('args=')
    expect(href).toContain('kwargs=')
    const url = new URL('http://t' + href)
    expect(url.searchParams.get('target')).toBe('web-*')
    expect(url.searchParams.get('fun')).toBe('state.apply')
  })

  it('shows a 502 panel with salt detail surfaced', async () => {
    server.use(
      http.get('/api/jobs/:jid', () =>
        HttpResponse.json({ detail: "Salt-API error 400: Client disabled: 'wheel'." }, { status: 502 }),
      ),
    )
    renderAt('j-bad')
    expect(await screen.findByText(/Salt-API responded with an error/i)).toBeInTheDocument()
    expect(screen.getByText(/Client disabled: 'wheel'/)).toBeInTheDocument()
  })

  it('shows a 404 panel for unknown jids', async () => {
    server.use(
      http.get('/api/jobs/:jid', () => HttpResponse.json({ detail: 'not found' }, { status: 404 })),
    )
    renderAt('nonexistent')
    expect(await screen.findByText(/is not in the master cache/i)).toBeInTheDocument()
  })

  it('shows the Kill job button when the job is incomplete', async () => {
    server.use(
      http.get('/api/jobs/:jid', () =>
        HttpResponse.json({
          jid: 'j-running',
          function: 'state.apply',
          arguments: [],
          kwargs: {},
          target: '*',
          target_type: 'glob',
          user: 'halite-service',
          start_time: '2025-10-19T12:00:00',
          minions: ['web-01', 'web-02'],
          results: [],
        }),
      ),
    )
    renderAt('j-running')
    expect(await screen.findByRole('button', { name: /kill job/i })).toBeInTheDocument()
  })

  it('hides the Kill job button when the job is complete', async () => {
    server.use(
      http.get('/api/jobs/:jid', () =>
        HttpResponse.json({
          jid: 'j-done',
          function: 'state.apply',
          arguments: [],
          kwargs: {},
          target: '*',
          target_type: 'glob',
          user: 'halite-service',
          start_time: '2025-10-19T12:00:00',
          minions: ['web-01'],
          results: [{ minion: 'web-01', success: true, retcode: 0, return_value: true }],
        }),
      ),
    )
    renderAt('j-done')
    await screen.findByText(/state\.apply on \*/i)
    expect(screen.queryByRole('button', { name: /kill job/i })).not.toBeInTheDocument()
  })

  it('switches to the by-state view when the toggle is clicked', async () => {
    const okMinion = {
      minion: 'web-01',
      success: true,
      retcode: 0,
      return_value: {
        'pkg_|-install_nginx_|-nginx_|-installed': {
          name: 'nginx', result: true, comment: 'OK', changes: {}, __run_num__: 0,
        },
        'service_|-nginx_running_|-nginx_|-running': {
          name: 'nginx', result: true, comment: 'Running', changes: {}, __run_num__: 1,
        },
      },
    }
    const failedMinion = {
      minion: 'web-02',
      success: false,
      retcode: 1,
      return_value: {
        'pkg_|-install_nginx_|-nginx_|-installed': {
          name: 'nginx', result: true, comment: 'OK', changes: {}, __run_num__: 0,
        },
        'service_|-nginx_running_|-nginx_|-running': {
          name: 'nginx', result: false, comment: 'Service failed to start', changes: {}, __run_num__: 1,
        },
      },
    }
    server.use(
      http.get('/api/jobs/:jid', () =>
        HttpResponse.json({
          jid: 'j-mixed-state',
          function: 'state.apply',
          arguments: [],
          kwargs: {},
          target: '*',
          target_type: 'glob',
          user: 'halite-service',
          start_time: '2025-10-19T12:00:00',
          minions: ['web-01', 'web-02'],
          results: [okMinion, failedMinion],
        }),
      ),
    )
    const user = userEvent.setup()
    renderAt('j-mixed-state')

    // Initial view is by-minion — minion buttons visible
    expect(await screen.findByRole('button', { name: /web-01/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /web-02/i })).toBeInTheDocument()

    // Click "By state"
    await user.click(screen.getByRole('button', { name: /^by state$/i }))

    // By-state view shows state IDs as primary content
    expect(await screen.findByText('install_nginx')).toBeInTheDocument()
    expect(screen.getByText('nginx_running')).toBeInTheDocument()
    // The state with a failure should be expanded by default → the failed
    // minion's comment is visible inside it
    expect(screen.getByText(/Service failed to start/)).toBeInTheDocument()
  })

  it('does not show the view toggle for non-highstate jobs', async () => {
    server.use(
      http.get('/api/jobs/:jid', () =>
        HttpResponse.json({
          jid: 'j-plain',
          function: 'test.ping',
          arguments: [],
          kwargs: {},
          target: '*',
          target_type: 'glob',
          user: 'halite-service',
          start_time: '2025-10-19T12:00:00',
          minions: ['web-01'],
          results: [{ minion: 'web-01', success: true, retcode: 0, return_value: true }],
        }),
      ),
    )
    renderAt('j-plain')
    await screen.findByRole('button', { name: /web-01/i })
    expect(screen.queryByRole('button', { name: /^by state$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^by minion$/i })).not.toBeInTheDocument()
  })
})

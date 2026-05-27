import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

// Mock TanStack Router's Link → plain anchor so we can assert the target.
const navigateSpy = vi.fn()
vi.mock('@tanstack/react-router', () => ({
  Link: ({
    children,
    to,
    params,
    ...rest
  }: {
    children?: React.ReactNode
    to: string
    params?: Record<string, string>
    [key: string]: unknown
  }) => {
    const href = to.replace(/\$(\w+)/g, (_, k: string) => params?.[k] ?? '')
    return (
      <a
        data-testid="router-link"
        href={href}
        onClick={(e) => {
          e.preventDefault()
          navigateSpy(href)
        }}
        {...rest}
      >
        {children}
      </a>
    )
  },
}))

import { TimelineGrid } from '@/features/jobs/timeline-grid'

import type { components } from '@/shared/api/types.gen'

type Timeline = components['schemas']['TimelineOut']
type Bar = components['schemas']['TimelineBar']

afterEach(() => navigateSpy.mockClear())

function makeBar(over: Partial<Bar> = {}): Bar {
  return {
    category: 'state',
    completed_at: new Date('2026-05-27T12:05:00Z').toISOString(),
    failed_minion_count: 0,
    function: 'state.apply',
    jid: '20260527120000000001',
    minion_count: 3,
    started_at: new Date('2026-05-27T12:00:00Z').toISOString(),
    status: 'pass',
    target: '*',
    user: 'saltapi',
    ...over,
  }
}

function makeTimeline(over: Partial<Timeline> = {}): Timeline {
  return {
    active_known: true,
    group_by: 'function',
    groups: [],
    last_polled_at: new Date('2026-05-27T13:00:00Z').toISOString(),
    total_bars: 0,
    window_end: new Date('2026-05-27T13:00:00Z').toISOString(),
    window_start: new Date('2026-05-27T12:00:00Z').toISOString(),
    ...over,
  }
}


describe('TimelineGrid', () => {
  it('renders one label row per group', () => {
    const data = makeTimeline({
      groups: [
        { bar_count: 2, bars: [makeBar(), makeBar({ jid: '20260527120000000002' })],
          category: 'state', key: 'state.apply', label: 'state.apply' },
        { bar_count: 1, bars: [makeBar({ category: 'test', function: 'test.ping', jid: 'B' })],
          category: 'test', key: 'test.ping', label: 'test.ping' },
      ],
      total_bars: 3,
    })
    render(<TimelineGrid data={data} />)
    expect(screen.getByText('state.apply')).toBeInTheDocument()
    expect(screen.getByText('test.ping')).toBeInTheDocument()
  })

  it('shows bar count in the gutter', () => {
    const data = makeTimeline({
      groups: [
        {
          bar_count: 5,
          bars: [makeBar(), makeBar({ jid: 'b' }), makeBar({ jid: 'c' }),
                 makeBar({ jid: 'd' }), makeBar({ jid: 'e' })],
          category: 'state',
          key: 'state.apply',
          label: 'state.apply',
        },
      ],
      total_bars: 5,
    })
    render(<TimelineGrid data={data} />)
    // The gutter shows the count to the right of the label
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('failed state bar uses destructive class', () => {
    const data = makeTimeline({
      groups: [
        {
          bar_count: 1,
          bars: [makeBar({ failed_minion_count: 2, status: 'failed' })],
          category: 'state',
          key: 'state.apply',
          label: 'state.apply',
        },
      ],
      total_bars: 1,
    })
    render(<TimelineGrid data={data} />)
    const link = screen.getByTestId('router-link')
    expect(link.className).toMatch(/destructive/)
  })

  it('click on a bar navigates to /jobs/{jid}', async () => {
    const data = makeTimeline({
      groups: [
        {
          bar_count: 1,
          bars: [makeBar({ jid: '20260527120000000077' })],
          category: 'state',
          key: 'state.apply',
          label: 'state.apply',
        },
      ],
      total_bars: 1,
    })
    render(<TimelineGrid data={data} />)
    const link = screen.getByTestId('router-link')
    await userEvent.click(link)
    expect(navigateSpy).toHaveBeenCalledWith('/jobs/20260527120000000077')
  })
})

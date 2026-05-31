import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import { useActivityStream } from '@/features/activity/use-activity-stream'

class MockEventSource {
  static instances: MockEventSource[] = []
  onmessage: ((e: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  url: string
  readyState = 0
  constructor(url: string) {
    this.url = url
    MockEventSource.instances.push(this)
  }
  emit(obj: unknown) {
    this.onmessage?.({ data: JSON.stringify(obj) })
  }
  close() {
    this.readyState = 2
  }
}

beforeEach(() => {
  MockEventSource.instances = []
  // @ts-expect-error test shim
  globalThis.EventSource = MockEventSource
})

function wrap() {
  const qc = new QueryClient()
  const spy = vi.spyOn(qc, 'invalidateQueries')
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  return { qc, spy, wrapper }
}

describe('useActivityStream', () => {
  it('invalidates jobs queries on a job event', async () => {
    const { spy, wrapper } = wrap()
    renderHook(() => useActivityStream(), { wrapper })
    const es = MockEventSource.instances[0]
    expect(es.url).toContain('/api/activity/stream')
    es.emit({ category: 'job', event_type: 'job.ret', jid: '20260529' })
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['jobs'] }),
      ),
    )
  })

  it('invalidates keys queries on a key event', async () => {
    const { spy, wrapper } = wrap()
    renderHook(() => useActivityStream(), { wrapper })
    MockEventSource.instances[0].emit({ category: 'key', event_type: 'key.accept' })
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['keys'] }),
      ),
    )
  })

  it('invalidates the activity root on every event', async () => {
    const { spy, wrapper } = wrap()
    renderHook(() => useActivityStream(), { wrapper })
    MockEventSource.instances[0].emit({ category: 'job', event_type: 'job.ret', jid: '20260529' })
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['activity'] }),
      ),
    )
  })
})

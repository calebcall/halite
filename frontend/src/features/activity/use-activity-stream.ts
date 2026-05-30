import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

export interface ActivityStreamEvent {
  category: 'job' | 'key' | 'minion'
  event_type: string
  minion_id?: string | null
  jid?: string | null
  fun?: string | null
  success?: boolean | null
  changed?: boolean | null
  summary?: string
}

const INVALIDATION: Record<ActivityStreamEvent['category'], string[][]> = {
  job: [['jobs']],
  key: [['keys']],
  minion: [['minions']],
}

/**
 * Subscribes to /api/activity/stream and invalidates the matching TanStack
 * Query caches on each event. Optional onEvent lets the feed UI also consume
 * the live event. EventSource auto-reconnects on drop.
 */
export function useActivityStream(onEvent?: (e: ActivityStreamEvent) => void) {
  const qc = useQueryClient()
  useEffect(() => {
    if (typeof EventSource === 'undefined') return
    const es = new EventSource('/api/activity/stream', { withCredentials: true })
    es.onmessage = (msg) => {
      let ev: ActivityStreamEvent
      try {
        ev = JSON.parse(msg.data)
      } catch {
        return
      }
      for (const queryKey of INVALIDATION[ev.category] ?? []) {
        void qc.invalidateQueries({ queryKey })
      }
      void qc.invalidateQueries({ queryKey: ['activity'] })
      onEvent?.(ev)
    }
    return () => es.close()
    // onEvent intentionally omitted from deps — callers pass inline; the stream
    // should not tear down/reconnect on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qc])
}

import { ExternalLink, Terminal } from 'lucide-react'

import { Button } from '@/components/ui/button'


export function MinionQuickActions({ minionId }: { minionId: string }) {
  // Plain <a> with hand-built URL — avoids TanStack Router's strict
  // typed `search` prop, and works regardless of whether the /run
  // page knows about the param yet (it can adopt later).
  const runHref = `/run?target=${encodeURIComponent(minionId)}&target_type=glob`
  return (
    <section className="flex flex-wrap gap-2">
      <Button asChild size="sm" variant="outline">
        <a href={runHref}>
          <Terminal className="mr-1.5 size-3" />
          Run command on this minion
        </a>
      </Button>
      <Button asChild size="sm" variant="ghost">
        <a href="/jobs">
          <ExternalLink className="mr-1.5 size-3" />
          Open Jobs
        </a>
      </Button>
    </section>
  )
}

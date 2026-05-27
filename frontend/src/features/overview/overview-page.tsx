import {
  Activity,
  ArrowRight,
  FileClock,
  Key,
  KeyRound,
  Play,
  Server,
  ServerCog,
  Shield,
  Terminal,
  Users,
} from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { useMemo, useState } from 'react'

import { ComplianceSparkline } from '@/features/fleet/compliance-sparkline'
import { FleetHeatmap } from '@/features/fleet/fleet-heatmap'
import { MinionRunPanel } from '@/features/fleet/minion-run-panel'
import { TopFailuresChart } from '@/features/fleet/top-failures-chart'
import { ApiError } from '@/shared/api/client'
import type { components } from '@/shared/api/types.gen'
import { useCurrentUser } from '@/features/auth/use-current-user'
import { useHasPerm } from '@/features/auth/use-has-perm'
import { useJobActivity } from '@/features/jobs/use-jobs'
import { useKeysList } from '@/features/keys/use-keys'
import { useMinionsList } from '@/features/minions/use-minions'

import { ChartCard, ChartEmpty, ChartSkeleton } from './chart-card'
import { JobActivityArea } from './job-activity-area'
import { KeyStatusBar } from './key-status-bar'
import { MinionStatusDonut } from './minion-status-donut'
import { StatCard } from './stat-card'

type Minion = components['schemas']['MinionHealthOut']

type Tile = {
  to: string
  label: string
  description: string
  icon: typeof Server
  requires?: { verb: string; resource: string }
}

const tiles: Tile[] = [
  {
    to: '/minions',
    label: 'Minions',
    description: 'Inspect connected minions and their grains.',
    icon: Server,
    requires: { verb: 'view', resource: 'minion:*' },
  },
  {
    to: '/keys',
    label: 'Keys',
    description: 'Accept, reject, or delete minion keys.',
    icon: Key,
    requires: { verb: 'view', resource: 'key:*' },
  },
  {
    to: '/jobs',
    label: 'Jobs',
    description: 'Browse recent salt jobs and their results.',
    icon: Activity,
    requires: { verb: 'view', resource: 'job:*' },
  },
  {
    to: '/run',
    label: 'Run',
    description: 'Execute a salt module function against a target.',
    icon: Terminal,
    requires: { verb: 'execute', resource: 'salt:*' },
  },
  {
    to: '/users',
    label: 'Users',
    description: 'Manage console accounts and their access.',
    icon: Users,
    requires: { verb: 'view', resource: 'user:*' },
  },
  {
    to: '/roles',
    label: 'Roles',
    description: 'Define role-based permissions for users.',
    icon: Shield,
    requires: { verb: 'view', resource: 'role:*' },
  },
  {
    to: '/audit',
    label: 'Audit',
    description: 'Review the system audit trail.',
    icon: FileClock,
    requires: { verb: 'view', resource: 'audit:*' },
  },
]

export function OverviewPage() {
  const { data: user } = useCurrentUser()
  const greeting = greetingFor(new Date().getHours())
  const name = user?.display_name?.split(' ')[0] || user?.username || ''

  const canViewMinions = useHasPerm('view', 'minion:*')
  const canViewKeys = useHasPerm('view', 'key:*')
  const canViewJobs = useHasPerm('view', 'job:*')

  const [selectedMinion, setSelectedMinion] = useState<Minion | null>(null)
  const [panelOpen, setPanelOpen] = useState(false)

  const handleTileClick = (m: Minion) => {
    setSelectedMinion(m)
    setPanelOpen(true)
  }

  return (
    <div className="flex flex-col gap-8">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
          Halite
        </p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">
          {greeting}{name ? `, ${name}` : ''}.
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          A Salt operations console. Live metrics refresh every 30 seconds.
        </p>
      </header>

      <section aria-label="Fleet health" className="flex flex-col gap-4">
        <FleetHeatmap onTileClick={handleTileClick} />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <ComplianceSparkline />
          <TopFailuresChart />
        </div>
      </section>

      <KpiRow
        canViewMinions={canViewMinions}
        canViewKeys={canViewKeys}
        canViewJobs={canViewJobs}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ChartCard
          title="Job activity"
          description="Jobs dispatched in the last 24 hours"
          className="lg:col-span-2"
        >
          <JobActivityPanel enabled={canViewJobs} />
        </ChartCard>

        <ChartCard
          title="Minion status"
          description="Live distribution across all states"
        >
          <MinionDonutPanel enabled={canViewMinions} />
        </ChartCard>

        <ChartCard
          title="Key inventory"
          description="Counts by approval state"
          className="lg:col-span-3"
        >
          <KeyBarPanel enabled={canViewKeys} />
        </ChartCard>
      </div>

      <section>
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.15em] text-muted-foreground">
          Sections
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {tiles.map((tile) => (
            <TileLink key={tile.to} tile={tile} />
          ))}
        </div>
      </section>

      <MinionRunPanel
        minion={selectedMinion}
        open={panelOpen}
        onOpenChange={setPanelOpen}
      />
    </div>
  )
}

function KpiRow({
  canViewMinions,
  canViewKeys,
  canViewJobs,
}: {
  canViewMinions: boolean
  canViewKeys: boolean
  canViewJobs: boolean
}) {
  const minions = useMinionsList()
  const keys = useKeysList()
  // The server pre-aggregates by hour so this scales past 500 jobs/day.
  const jobs = useJobActivity(24)

  const minionMetrics = useMemo(() => {
    if (!minions.data) return { online: 0, total: 0 }
    let online = 0
    for (const m of minions.data.minions) {
      if (m.status === 'online') online++
    }
    return { online, total: minions.data.total }
  }, [minions.data])

  const pendingKeys = useMemo(() => {
    if (!keys.data) return 0
    return keys.data.keys.reduce(
      (acc, k) => acc + (k.status === 'pending' ? 1 : 0),
      0,
    )
  }, [keys.data])

  const jobMetrics = {
    running: jobs.data?.running ?? 0,
    last24h: jobs.data?.total ?? 0,
  }

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatCard
        label="Online minions"
        value={
          canViewMinions
            ? `${minionMetrics.online}${minionMetrics.total ? ` / ${minionMetrics.total}` : ''}`
            : '—'
        }
        hint={canViewMinions ? 'Currently connected' : 'No access'}
        icon={ServerCog}
        tone="success"
        loading={canViewMinions && minions.isPending}
      />
      <StatCard
        label="Pending keys"
        value={canViewKeys ? pendingKeys : '—'}
        hint={canViewKeys ? 'Awaiting approval' : 'No access'}
        icon={KeyRound}
        tone={pendingKeys > 0 ? 'amber' : 'muted'}
        loading={canViewKeys && keys.isPending}
      />
      <StatCard
        label="Running jobs"
        value={canViewJobs ? jobMetrics.running : '—'}
        hint={canViewJobs ? 'In flight right now' : 'No access'}
        icon={Play}
        tone={jobMetrics.running > 0 ? 'amber' : 'muted'}
        loading={canViewJobs && jobs.isPending}
      />
      <StatCard
        label="Jobs · 24h"
        value={canViewJobs ? jobMetrics.last24h : '—'}
        hint={canViewJobs ? 'Dispatched today' : 'No access'}
        icon={Activity}
        tone="amber"
        loading={canViewJobs && jobs.isPending}
      />
    </div>
  )
}

function MinionDonutPanel({ enabled }: { enabled: boolean }) {
  const { data, isPending, error } = useMinionsList()
  if (!enabled) {
    return <ChartEmpty message="You don't have permission to view minions." />
  }
  if (error) return <ChartUnavailable error={error} subject="minions" />
  if (isPending) return <ChartSkeleton />
  if (!data || data.total === 0)
    return <ChartEmpty message="No minions known to the master yet." />
  return <MinionStatusDonut minions={data.minions} />
}

function JobActivityPanel({ enabled }: { enabled: boolean }) {
  const { data, isPending, error } = useJobActivity(24)
  if (!enabled) {
    return <ChartEmpty message="You don't have permission to view jobs." />
  }
  if (error) return <ChartUnavailable error={error} subject="jobs" />
  if (isPending) return <ChartSkeleton />
  if (!data) return <ChartEmpty message="No job data available." />
  return <JobActivityArea buckets={data.buckets} />
}

function KeyBarPanel({ enabled }: { enabled: boolean }) {
  const { data, isPending, error } = useKeysList()
  if (!enabled) {
    return <ChartEmpty message="You don't have permission to view keys." />
  }
  if (error) return <ChartUnavailable error={error} subject="keys" />
  if (isPending) return <ChartSkeleton />
  if (!data || data.keys.length === 0)
    return <ChartEmpty message="No keys known to the master." />
  return <KeyStatusBar keys={data.keys} />
}

function ChartUnavailable({
  error,
  subject,
}: {
  error: unknown
  subject: string
}) {
  if (error instanceof ApiError && error.status === 503) {
    return (
      <ChartEmpty message="Salt-API is not configured. Check your environment variables." />
    )
  }
  if (error instanceof ApiError && error.isForbidden) {
    return (
      <ChartEmpty
        message={`You don't have permission to view ${subject}.`}
      />
    )
  }
  return <ChartEmpty message={`Could not load ${subject}.`} />
}

function TileLink({ tile }: { tile: Tile }) {
  const allowed = useHasPerm(
    tile.requires?.verb ?? '*',
    tile.requires?.resource ?? '*',
  )
  if (tile.requires && !allowed) return null
  const Icon = tile.icon
  return (
    <Link
      to={tile.to}
      className="group relative flex flex-col gap-3 rounded-lg border border-border/80 bg-card p-4 transition-colors hover:border-primary/50 hover:bg-accent"
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary ring-1 ring-primary/25">
        <Icon className="h-4 w-4" />
      </span>
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-semibold text-foreground">{tile.label}</span>
          <ArrowRight className="h-3.5 w-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {tile.description}
        </p>
      </div>
    </Link>
  )
}

function greetingFor(hour: number): string {
  if (hour < 5) return 'Working late'
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

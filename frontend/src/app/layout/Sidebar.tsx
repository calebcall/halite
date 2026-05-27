// frontend/src/app/layout/Sidebar.tsx
import {
  Activity,
  FileClock,
  Info,
  Key,
  LineChart,
  Menu,
  PackageSearch,
  Server,
  Shield,
  SlidersHorizontal,
  Terminal,
  Users,
} from 'lucide-react'
import { Link, useRouterState } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import { useHasPerm } from '@/features/auth/use-has-perm'
import { BrandMark } from './BrandMark'

type NavItem = {
  to: string
  label: string
  icon: typeof Server
  /** If undefined, item is always shown. If set, item only shows when the user has the permission. */
  requires?: { verb: string; resource: string }
  /** If true, the item is always shown but rendered as disabled (feature not yet built). */
  comingSoon?: boolean
}

type NavSection = {
  label: string
  items: NavItem[]
}

const navSections: NavSection[] = [
  {
    label: 'Infrastructure',
    items: [
      { to: '/', label: 'Overview', icon: Server },
      { to: '/minions', label: 'Minions', icon: Server, requires: { verb: 'view', resource: 'minion:*' } },
      { to: '/keys', label: 'Keys', icon: Key, requires: { verb: 'view', resource: 'key:*' } },
    ],
  },
  {
    label: 'Operations',
    items: [
      { to: '/jobs', label: 'Jobs', icon: Activity, requires: { verb: 'view', resource: 'job:*' } },
      { to: '/jobs/timeline', label: 'Timeline', icon: LineChart, requires: { verb: 'view', resource: 'job:*' } },
      { to: '/run', label: 'Run', icon: Terminal, requires: { verb: 'execute', resource: 'salt:*' } },
      {
        to: '/inventory',
        label: 'Inventory',
        icon: PackageSearch,
        requires: { verb: 'view', resource: 'inventory:*' },
      },
    ],
  },
  {
    label: 'Administration',
    items: [
      { to: '/users', label: 'Users', icon: Users, requires: { verb: 'view', resource: 'user:*' } },
      { to: '/roles', label: 'Roles', icon: Shield, requires: { verb: 'view', resource: 'role:*' } },
      { to: '/audit', label: 'Audit', icon: FileClock, requires: { verb: 'view', resource: 'audit:*' } },
      {
        to: '/admin/settings',
        label: 'Settings',
        icon: SlidersHorizontal,
        requires: { verb: 'manage', resource: 'settings:*' },
      },
      // About is intentionally ungated — any signed-in user can read the colophon.
      { to: '/about', label: 'About', icon: Info },
    ],
  },
]

/** Desktop sidebar — visible only at lg and up. */
export function Sidebar() {
  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground lg:flex">
      <SidebarHeader />
      <SidebarNav />
    </aside>
  )
}

/**
 * Mobile drawer trigger. Renders a hamburger button — when tapped, slides the
 * sidebar in from the left. Auto-dismisses when the user navigates to a new
 * route, so they don't have to swipe-close after every tap.
 */
export function MobileSidebar() {
  const [open, setOpen] = useState(false)
  const pathname = useRouterState({ select: (s) => s.location.pathname })

  // Close on route change. Watching pathname rather than wiring up an onClick
  // on every NavLink because TanStack's <Link> may navigate without a
  // synchronous click (e.g. programmatic navigate from elsewhere).
  useEffect(() => {
    setOpen(false)
  }, [pathname])

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-10 w-10 lg:hidden"
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="flex w-72 flex-col p-0" showClose={false}>
        {/* Required for Radix a11y — visually hidden but announced to SR. */}
        <SheetTitle className="sr-only">Navigation</SheetTitle>
        <SheetDescription className="sr-only">
          Jump to a section of Halite.
        </SheetDescription>
        <SidebarHeader />
        <SidebarNav />
      </SheetContent>
    </Sheet>
  )
}

function SidebarHeader() {
  return (
    <div className="flex h-14 items-center gap-2.5 border-b border-sidebar-border px-4">
      <BrandMark className="h-8 w-8" />
      <div className="flex flex-col leading-tight">
        <span className="text-sm font-semibold tracking-tight text-foreground">
          Halite
        </span>
        <span className="text-[10px] uppercase tracking-[0.15em] text-sidebar-muted">
          Salt Console
        </span>
      </div>
    </div>
  )
}

function SidebarNav() {
  return (
    <nav className="flex-1 overflow-y-auto px-3 py-4">
      {navSections.map((section) => (
        <NavSection key={section.label} section={section} />
      ))}
    </nav>
  )
}

function NavSection({ section }: { section: NavSection }) {
  return (
    <div className="mb-5">
      <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.15em] text-sidebar-muted">
        {section.label}
      </p>
      <div className="flex flex-col gap-0.5">
        {section.items.map((item) => (
          <NavLink key={item.to} item={item} />
        ))}
      </div>
    </div>
  )
}

function NavLink({ item }: { item: NavItem }) {
  // Hooks must be called unconditionally — pass a no-op spec when not required.
  const allowed = useHasPerm(
    item.requires?.verb ?? '*',
    item.requires?.resource ?? '*',
  )
  const Icon = item.icon
  // Touch-friendly: 40px tall on mobile (more than the desktop 36px), still
  // visually compact. min-h locks the row so labels never crowd touch area.
  const baseRow =
    'group relative flex min-h-10 items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors'
  if (item.comingSoon) {
    return (
      <span
        className={cn(baseRow, 'cursor-not-allowed text-sidebar-muted/70')}
        title="Available in a later plan"
      >
        <Icon className="h-4 w-4" />
        {item.label}
      </span>
    )
  }
  if (item.requires && !allowed) return null
  return (
    <Link
      to={item.to}
      className={cn(
        baseRow,
        'text-sidebar-foreground hover:bg-sidebar-accent/10 hover:text-foreground',
      )}
      activeOptions={{ exact: item.to === '/' }}
      activeProps={{
        className:
          'bg-sidebar-accent/15 text-foreground font-medium before:absolute before:left-0 before:top-1.5 before:bottom-1.5 before:w-[3px] before:rounded-r before:bg-sidebar-accent',
      }}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span className="truncate">{item.label}</span>
    </Link>
  )
}

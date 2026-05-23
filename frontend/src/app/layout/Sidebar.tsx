// frontend/src/app/layout/Sidebar.tsx
import { Activity, FileClock, Key, Server, Shield, Terminal, Users } from 'lucide-react'
import { Link } from '@tanstack/react-router'

import { useHasPerm } from '@/features/auth/use-has-perm'

type NavItem = {
  to: string
  label: string
  icon: typeof Server
  /** If undefined, item is always shown. If set, item only shows when the user has the permission. */
  requires?: { verb: string; resource: string }
  /** If true, the item is always shown but rendered as disabled (feature not yet built). */
  comingSoon?: boolean
}

const navItems: NavItem[] = [
  { to: '/', label: 'Overview', icon: Server },
  { to: '/minions', label: 'Minions', icon: Server, requires: { verb: 'view', resource: 'minion:*' } },
  { to: '/keys', label: 'Keys', icon: Key, requires: { verb: 'view', resource: 'key:*' } },
  { to: '/jobs', label: 'Jobs', icon: Activity, requires: { verb: 'view', resource: 'job:*' } },
  { to: '/run', label: 'Run', icon: Terminal, requires: { verb: 'execute', resource: 'salt:*' } },
  { to: '/users', label: 'Users', icon: Users, requires: { verb: 'view', resource: 'user:*' } },
  { to: '/roles', label: 'Roles', icon: Shield, requires: { verb: 'view', resource: 'role:*' } },
  { to: '/audit', label: 'Audit', icon: FileClock, requires: { verb: 'view', resource: 'audit:*' } },
]

export function Sidebar() {
  return (
    <aside className="w-56 shrink-0 border-r bg-muted/30 p-2">
      <nav className="flex flex-col gap-1">
        {navItems.map((item) => (
          <NavLink key={item.to} item={item} />
        ))}
      </nav>
    </aside>
  )
}

function NavLink({ item }: { item: NavItem }) {
  // Hooks must be called unconditionally — pass a no-op spec when not required.
  const allowed = useHasPerm(
    item.requires?.verb ?? '*',
    item.requires?.resource ?? '*',
  )
  const Icon = item.icon
  if (item.comingSoon) {
    return (
      <span
        className="flex cursor-not-allowed items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground/60"
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
      className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-muted"
      activeProps={{ className: 'bg-muted font-medium' }}
    >
      <Icon className="h-4 w-4" />
      {item.label}
    </Link>
  )
}

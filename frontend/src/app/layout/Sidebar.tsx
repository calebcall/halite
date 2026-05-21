import { Activity, FileClock, Key, Server, Users } from 'lucide-react'
import { Link } from '@tanstack/react-router'

const navItems = [
  { to: '/', label: 'Overview', icon: Server, enabled: true },
  { to: '/minions', label: 'Minions', icon: Server, enabled: false },
  { to: '/keys', label: 'Keys', icon: Key, enabled: false },
  { to: '/jobs', label: 'Jobs', icon: Activity, enabled: false },
  { to: '/users', label: 'Users', icon: Users, enabled: true },
  { to: '/audit', label: 'Audit', icon: FileClock, enabled: false },
]

export function Sidebar() {
  return (
    <aside className="w-56 shrink-0 border-r bg-muted/30 p-2">
      <nav className="flex flex-col gap-1">
        {navItems.map((item) => {
          const Icon = item.icon
          if (!item.enabled) {
            return (
              <span
                key={item.to}
                className="flex cursor-not-allowed items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground/60"
                title="Available in a later plan"
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </span>
            )
          }
          return (
            <Link
              key={item.to}
              to={item.to}
              className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-muted"
              activeProps={{ className: 'bg-muted font-medium' }}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}

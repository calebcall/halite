import { Outlet, useNavigate } from '@tanstack/react-router'

import { useActivityStream } from '@/features/activity/use-activity-stream'
import { useAuthActions, useCurrentUser } from '@/features/auth/use-current-user'
import { useSiteConfig } from '@/features/auth/use-site-config'
import { DemoBanner } from './DemoBanner'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

export function AppShell() {
  useActivityStream()
  const { data: config } = useSiteConfig()
  const { data: user } = useCurrentUser()
  const { logout } = useAuthActions()
  const navigate = useNavigate()

  const isAdmin = !!user && user.username !== 'demo'

  async function signInAsAdmin() {
    await logout()
    void navigate({ to: '/login' })
  }

  return (
    <div className="flex min-h-dvh bg-background text-foreground">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <DemoBanner demo={config?.demo ?? false} isAdmin={isAdmin} onSignIn={signInAsAdmin} />
        <main className="flex-1 overflow-auto">
          <div className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

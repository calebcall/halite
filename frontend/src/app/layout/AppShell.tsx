import { Outlet } from '@tanstack/react-router'

import { useActivityStream } from '@/features/activity/use-activity-stream'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

export function AppShell() {
  useActivityStream()
  return (
    <div className="flex min-h-dvh bg-background text-foreground">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex-1 overflow-auto">
          <div className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

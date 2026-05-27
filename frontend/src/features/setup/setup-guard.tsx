import { Navigate, useRouterState } from '@tanstack/react-router'
import { type ReactNode } from 'react'

import { useSettingsStatus } from '@/features/admin/use-settings'

const EXEMPT_PATHS = ['/login', '/change-password', '/setup']

export function SetupGuard({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const { data, isLoading } = useSettingsStatus()

  if (EXEMPT_PATHS.some((p) => pathname.startsWith(p))) {
    return <>{children}</>
  }
  // Brief null while status loads (~100ms). Avoids a flash of the app shell
  // on first render before we know whether setup is needed.
  if (isLoading) return null
  if (data && !data.configured) {
    return <Navigate to="/setup" replace />
  }
  return <>{children}</>
}

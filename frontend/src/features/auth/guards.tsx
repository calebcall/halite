import { Navigate } from '@tanstack/react-router'
import { type ReactNode, useEffect, useRef } from 'react'

import { useSiteConfig } from './use-site-config'
import { useAuthActions, useCurrentUser } from './use-current-user'

function FullPageSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center text-muted-foreground">
      Loading…
    </div>
  )
}

export function LoginRequired({ children }: { children: ReactNode }) {
  const { data, isPending } = useCurrentUser()
  const { data: config } = useSiteConfig()
  const { demoLogin } = useAuthActions()
  const tried = useRef(false)

  const needDemoLogin = !isPending && !data && config?.demo === true
  useEffect(() => {
    if (needDemoLogin && !tried.current) {
      tried.current = true
      void demoLogin().catch(() => {})
    }
  }, [needDemoLogin, demoLogin])

  if (isPending) return <FullPageSpinner />
  if (!data) {
    return config?.demo ? <FullPageSpinner /> : <Navigate to="/login" replace />
  }
  return <>{children}</>
}

export function PublicOnly({ children }: { children: ReactNode }) {
  const { data, isPending } = useCurrentUser()
  if (isPending) return <FullPageSpinner />
  if (data) return <Navigate to="/" replace />
  return <>{children}</>
}

export function MustChangePassword({ children }: { children: ReactNode }) {
  const { data } = useCurrentUser()
  if (data?.must_change_pw) {
    return <Navigate to="/change-password" replace />
  }
  return <>{children}</>
}

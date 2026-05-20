import { Navigate } from '@tanstack/react-router'
import { type ReactNode } from 'react'

import { useCurrentUser } from './use-current-user'

function FullPageSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center text-muted-foreground">
      Loading…
    </div>
  )
}

export function LoginRequired({ children }: { children: ReactNode }) {
  const { data, isPending } = useCurrentUser()
  if (isPending) return <FullPageSpinner />
  if (!data) return <Navigate to="/login" replace />
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

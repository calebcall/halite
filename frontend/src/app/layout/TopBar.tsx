import { LogOut } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useAuthActions, useCurrentUser } from '@/features/auth/use-current-user'

export function TopBar() {
  const { data: user } = useCurrentUser()
  const { logout } = useAuthActions()

  return (
    <header className="flex h-14 items-center justify-between border-b bg-background px-4">
      <div className="flex items-center gap-3">
        <span className="font-semibold tracking-tight">Halite</span>
      </div>
      <div className="flex items-center gap-3 text-sm text-muted-foreground">
        {user && <span>{user.display_name || user.username}</span>}
        <Button size="sm" variant="ghost" onClick={() => void logout()}>
          <LogOut className="mr-2 h-4 w-4" />
          Sign out
        </Button>
      </div>
    </header>
  )
}

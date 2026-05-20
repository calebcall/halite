import { UserMenu } from './UserMenu'

export function TopBar() {
  return (
    <header className="flex h-14 items-center justify-between border-b bg-background px-4">
      <div className="flex items-center gap-3">
        <span className="font-semibold tracking-tight">Halite</span>
      </div>
      <UserMenu />
    </header>
  )
}

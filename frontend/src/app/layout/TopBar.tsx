import { BrandMark } from './BrandMark'
import { MobileSidebar } from './Sidebar'
import { UserMenu } from './UserMenu'

export function TopBar() {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-2 border-b border-border bg-background/95 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/75 sm:px-4 md:px-6">
      <div className="flex items-center gap-2">
        <MobileSidebar />
        {/*
          Brand label is shown only when the desktop sidebar (which already
          carries the wordmark) is hidden, so we don't double up on lg+ screens.
        */}
        <div className="flex items-center gap-2 lg:hidden">
          <BrandMark className="h-7 w-7" />
          <span className="text-sm font-semibold tracking-tight">Halite</span>
        </div>
      </div>
      <UserMenu />
    </header>
  )
}

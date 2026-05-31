type DemoBannerProps = {
  demo: boolean
  isAdmin: boolean
  onSignIn: () => void
}

export function DemoBanner({ demo, isAdmin, onSignIn }: DemoBannerProps) {
  if (!demo) return null
  return (
    <div className="flex items-center justify-center gap-3 bg-primary/15 px-4 py-1.5 text-center text-sm text-primary">
      <span>
        <strong>Demo mode</strong>{' '}
        {isAdmin ? '— signed in as admin (changes enabled)' : '— read-only'}
      </span>
      {!isAdmin && (
        <button type="button" onClick={onSignIn} className="font-semibold underline underline-offset-2">
          Sign in as admin
        </button>
      )}
    </div>
  )
}

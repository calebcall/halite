import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DemoBanner } from '@/app/layout/DemoBanner'

describe('DemoBanner', () => {
  it('renders nothing when not in demo mode', () => {
    const { container } = render(<DemoBanner demo={false} isAdmin={false} onSignIn={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows read-only label + sign-in for the demo user', () => {
    render(<DemoBanner demo={true} isAdmin={false} onSignIn={() => {}} />)
    expect(screen.getByText(/demo mode/i)).toBeInTheDocument()
    expect(screen.getByText(/read-only/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in as admin/i })).toBeInTheDocument()
  })

  it('shows admin label and no sign-in button when admin', () => {
    render(<DemoBanner demo={true} isAdmin={true} onSignIn={() => {}} />)
    expect(screen.getByText(/admin/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /sign in as admin/i })).toBeNull()
  })
})

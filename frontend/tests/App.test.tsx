import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { LoginPage } from '@/features/auth/login-page'

const server = setupServer(
  http.post('/api/auth/login', async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string }
    if (body.username === 'admin' && body.password === 'changeme') {
      return HttpResponse.json({
        username: 'admin',
        display_name: 'admin',
        must_change_pw: true,
      })
    }
    return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 })
  }),
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

describe('LoginPage', () => {
  it('renders the form', () => {
    renderWithProviders(<LoginPage />)
    expect(screen.getByRole('heading', { name: /sign in to halite/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  })

  it('shows server error on bad credentials', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LoginPage />)

    await user.type(screen.getByLabelText(/username/i), 'admin')
    await user.type(screen.getByLabelText(/password/i), 'wrong')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByText(/invalid username or password/i)).toBeInTheDocument()
    })
  })
})

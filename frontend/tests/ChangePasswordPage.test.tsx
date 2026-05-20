// frontend/tests/ChangePasswordPage.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { ChangePasswordPage } from '@/features/auth/change-password-page'

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin',
      display_name: 'admin',
      must_change_pw: false,
    }),
  ),
  http.post('/api/auth/change-password', async ({ request }) => {
    const body = (await request.json()) as { current_password: string; new_password: string }
    if (body.current_password === 'oldpw-fine' && body.new_password === 'newpw-fine') {
      return new HttpResponse(null, { status: 204 })
    }
    return HttpResponse.json({ detail: 'Current password is incorrect' }, { status: 403 })
  }),
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function renderInRouter() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const rootRoute = createRootRoute({ component: Outlet })
  const homeRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    component: () => <ChangePasswordPage />,
  })
  const router = createRouter({ routeTree: rootRoute.addChildren([homeRoute]) })
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('ChangePasswordPage', () => {
  it('renders the form', async () => {
    renderInRouter()
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /change password/i })).toBeInTheDocument(),
    )
    expect(screen.getByLabelText(/current password/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^new password$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/confirm new password/i)).toBeInTheDocument()
  })

  it('validates that new + confirm match', async () => {
    const user = userEvent.setup()
    renderInRouter()
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /change password/i })).toBeInTheDocument(),
    )
    await user.type(screen.getByLabelText(/current password/i), 'oldpw-fine')
    await user.type(screen.getByLabelText(/^new password$/i), 'newpw-fine')
    await user.type(screen.getByLabelText(/confirm new password/i), 'mismatch')
    await user.click(screen.getByRole('button', { name: /update password/i }))
    expect(await screen.findByText(/must match/i)).toBeInTheDocument()
  })

  it('shows server error when current password is wrong', async () => {
    const user = userEvent.setup()
    renderInRouter()
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /change password/i })).toBeInTheDocument(),
    )
    await user.type(screen.getByLabelText(/current password/i), 'WRONG')
    await user.type(screen.getByLabelText(/^new password$/i), 'newpw-fine')
    await user.type(screen.getByLabelText(/confirm new password/i), 'newpw-fine')
    await user.click(screen.getByRole('button', { name: /update password/i }))
    expect(await screen.findByText(/current password is incorrect/i)).toBeInTheDocument()
  })

  it('shows success message on happy path', async () => {
    const user = userEvent.setup()
    renderInRouter()
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /change password/i })).toBeInTheDocument(),
    )
    await user.type(screen.getByLabelText(/current password/i), 'oldpw-fine')
    await user.type(screen.getByLabelText(/^new password$/i), 'newpw-fine')
    await user.type(screen.getByLabelText(/confirm new password/i), 'newpw-fine')
    await user.click(screen.getByRole('button', { name: /update password/i }))
    expect(await screen.findByText(/password updated/i)).toBeInTheDocument()
  })
})

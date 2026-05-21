// frontend/tests/CreateUserDialog.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { CreateUserDialog } from '@/features/users/create-user-dialog'

let createCalls: Array<Record<string, unknown>> = []

const server = setupServer(
  http.get('/api/roles', () =>
    HttpResponse.json({
      total: 1,
      roles: [
        { id: '11111111-1111-1111-1111-111111111111', name: 'operator', is_builtin: true, description: '' },
      ],
    }),
  ),
  http.post('/api/users', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>
    createCalls.push(body)
    return HttpResponse.json(
      {
        id: 'new',
        username: body.username,
        display_name: body.display_name ?? '',
        email: body.email ?? null,
        is_active: true,
        is_builtin: false,
        must_change_pw: body.must_change_pw ?? true,
        created_at: '2026-05-19T00:00:00Z',
        last_login_at: null,
      },
      { status: 201 },
    )
  }),
)

beforeAll(() => server.listen())
afterEach(() => {
  server.resetHandlers()
  createCalls = []
})
afterAll(() => server.close())

function renderDialog() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <CreateUserDialog open onOpenChange={() => {}} />
    </QueryClientProvider>,
  )
}

describe('CreateUserDialog', () => {
  it('submits a valid form', async () => {
    const user = userEvent.setup()
    renderDialog()
    await user.type(screen.getByLabelText(/username/i), 'alice')
    await user.type(screen.getByLabelText(/initial password/i), 'hunter2-strong')
    await user.click(screen.getByRole('button', { name: /create user/i }))

    await waitFor(() => expect(createCalls).toHaveLength(1))
    expect(createCalls[0]).toMatchObject({
      username: 'alice',
      password: 'hunter2-strong',
      must_change_pw: true,
      role_ids: [],
    })
  })

  it('shows 409 on duplicate username', async () => {
    server.use(
      http.post('/api/users', () =>
        HttpResponse.json({ detail: 'Username already exists' }, { status: 409 }),
      ),
    )
    const user = userEvent.setup()
    renderDialog()
    await user.type(screen.getByLabelText(/username/i), 'admin')
    await user.type(screen.getByLabelText(/initial password/i), 'hunter2-strong')
    await user.click(screen.getByRole('button', { name: /create user/i }))
    expect(await screen.findByText(/already exists/i)).toBeInTheDocument()
  })
})

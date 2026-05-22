// frontend/tests/KeyActionDialog.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { KeyActionDialog } from '@/features/keys/key-action-dialog'

let lastPostedPath: string | null = null
let lastDeletedPath: string | null = null

const server = setupServer(
  http.post('/api/keys/:keyId/accept', ({ request }) => {
    lastPostedPath = new URL(request.url).pathname
    return new HttpResponse(null, { status: 204 })
  }),
  http.post('/api/keys/:keyId/reject', ({ request }) => {
    lastPostedPath = new URL(request.url).pathname
    return new HttpResponse(null, { status: 204 })
  }),
  http.delete('/api/keys/:keyId', ({ request }) => {
    lastDeletedPath = new URL(request.url).pathname
    return new HttpResponse(null, { status: 204 })
  }),
)

beforeAll(() => server.listen())
afterEach(() => {
  server.resetHandlers()
  lastPostedPath = null
  lastDeletedPath = null
})
afterAll(() => server.close())

function renderDialog(action: 'accept' | 'reject' | 'delete') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <KeyActionDialog keyId="web-01" action={action} open onOpenChange={() => {}} />
    </QueryClientProvider>,
  )
}

describe('KeyActionDialog', () => {
  it('confirms an accept', async () => {
    const user = userEvent.setup()
    renderDialog('accept')
    await user.click(screen.getByRole('button', { name: /accept key/i }))
    await waitFor(() => {
      expect(lastPostedPath).toBe('/api/keys/web-01/accept')
    })
  })

  it('confirms a reject', async () => {
    const user = userEvent.setup()
    renderDialog('reject')
    await user.click(screen.getByRole('button', { name: /reject key/i }))
    await waitFor(() => {
      expect(lastPostedPath).toBe('/api/keys/web-01/reject')
    })
  })

  it('confirms a delete', async () => {
    const user = userEvent.setup()
    renderDialog('delete')
    await user.click(screen.getByRole('button', { name: /delete key/i }))
    await waitFor(() => {
      expect(lastDeletedPath).toBe('/api/keys/web-01')
    })
  })

  it('shows a 403 error', async () => {
    server.use(
      http.delete('/api/keys/:keyId', () =>
        HttpResponse.json({ detail: 'Forbidden' }, { status: 403 }),
      ),
    )
    const user = userEvent.setup()
    renderDialog('delete')
    await user.click(screen.getByRole('button', { name: /delete key/i }))
    expect(await screen.findByText(/don'?t have permission/i)).toBeInTheDocument()
  })
})

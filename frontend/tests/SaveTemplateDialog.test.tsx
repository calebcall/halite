// frontend/tests/SaveTemplateDialog.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { SaveTemplateDialog } from '@/features/run/save-template-dialog'

let lastBody: unknown = null
const server = setupServer(
  http.post('/api/templates', async ({ request }) => {
    lastBody = await request.json()
    return HttpResponse.json({
      id: 't-new', name: (lastBody as { name: string }).name, description: '',
      target: '*', target_type: 'glob', fun: 'test.ping', args: [], kwargs: {},
      created_at: '2026-05-26T10:00:00Z', updated_at: '2026-05-26T10:00:00Z',
    }, { status: 201 })
  }),
)

beforeAll(() => server.listen())
afterEach(() => {
  server.resetHandlers()
  lastBody = null
})
afterAll(() => server.close())

const SAMPLE_BODY = {
  target: '*', target_type: 'glob', fun: 'test.ping', args: [], kwargs: {},
}

function renderDialog() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const onOpenChange = vi.fn()
  return {
    onOpenChange,
    ...render(
      <QueryClientProvider client={qc}>
        <SaveTemplateDialog open onOpenChange={onOpenChange} body={SAMPLE_BODY} />
      </QueryClientProvider>,
    ),
  }
}

describe('SaveTemplateDialog', () => {
  it('saves with a valid name and closes', async () => {
    const user = userEvent.setup()
    const { onOpenChange } = renderDialog()
    await user.type(screen.getByLabelText(/^name$/i), 'My template')
    await user.click(screen.getByRole('button', { name: /save template/i }))
    await waitFor(() => {
      expect(lastBody).toMatchObject({ name: 'My template', target: '*', fun: 'test.ping' })
    })
    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false)
    })
  })

  it('shows a validation error when name is empty', async () => {
    const user = userEvent.setup()
    renderDialog()
    await user.click(screen.getByRole('button', { name: /save template/i }))
    expect(await screen.findByText(/name is required/i)).toBeInTheDocument()
    expect(lastBody).toBeNull()
  })

  it('sends is_shared=true when the share switch is toggled on before saving', async () => {
    const user = userEvent.setup()
    renderDialog()
    await user.type(screen.getByLabelText(/^name$/i), 'Shared template')
    await user.click(screen.getByRole('switch', { name: /share with team/i }))
    await user.click(screen.getByRole('button', { name: /save template/i }))
    await waitFor(() => {
      expect(lastBody).toMatchObject({ name: 'Shared template', is_shared: true })
    })
  })
})

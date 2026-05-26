// frontend/tests/TemplatePicker.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { TemplatePicker } from '@/features/run/template-picker'
import type { CommandTemplate } from '@/features/run/use-templates'

const sampleTemplates: CommandTemplate[] = [
  {
    id: 't1', name: 'Web dry-run', description: 'Dry-run on web-*',
    target: 'web-*', target_type: 'glob', fun: 'state.highstate',
    args: [], kwargs: { test: 'True' },
    created_at: '2026-05-26T10:00:00Z', updated_at: '2026-05-26T10:00:00Z',
  },
]

const server = setupServer(
  http.get('/api/templates', () =>
    HttpResponse.json({ total: 1, templates: sampleTemplates }),
  ),
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function renderPicker(onSelect = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return {
    onSelect,
    ...render(
      <QueryClientProvider client={qc}>
        <TemplatePicker onSelect={onSelect} />
      </QueryClientProvider>,
    ),
  }
}

describe('TemplatePicker', () => {
  it('shows templates in the dropdown', async () => {
    const user = userEvent.setup()
    renderPicker()
    await user.click(await screen.findByRole('combobox'))
    expect(await screen.findByText('Web dry-run')).toBeInTheDocument()
  })

  it('calls onSelect with the template payload', async () => {
    const onSelect = vi.fn()
    const user = userEvent.setup()
    renderPicker(onSelect)
    await user.click(await screen.findByRole('combobox'))
    await user.click(await screen.findByText('Web dry-run'))
    await waitFor(() => {
      expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({
        name: 'Web dry-run',
        target: 'web-*',
        fun: 'state.highstate',
      }))
    })
  })

  it('shows the placeholder when no templates exist', async () => {
    server.use(
      http.get('/api/templates', () => HttpResponse.json({ total: 0, templates: [] })),
    )
    renderPicker()
    expect(await screen.findByText(/No templates yet/i)).toBeInTheDocument()
  })
})

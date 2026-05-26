// frontend/tests/TemplatePicker.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { TemplatePicker } from '@/features/run/template-picker'
import type { CommandTemplate } from '@/features/run/use-templates'

// ─── fixtures ────────────────────────────────────────────────────────────────

const ALICE_ME = {
  username: 'alice',
  display_name: 'Alice',
  must_change_pw: false,
  permissions: [],
}

const aliceTemplate: CommandTemplate = {
  id: 't-alice',
  name: 'Alice template',
  description: '',
  target: '*',
  target_type: 'glob',
  fun: 'test.ping',
  args: [],
  kwargs: {},
  is_shared: false,
  owner_user_id: 'uid-alice',
  owner_username: 'alice',
  created_at: '2026-05-26T10:00:00Z',
  updated_at: '2026-05-26T10:00:00Z',
}

const bobTemplate: CommandTemplate = {
  id: 't-bob',
  name: 'Bob shared template',
  description: '',
  target: 'web-*',
  target_type: 'glob',
  fun: 'state.highstate',
  args: [],
  kwargs: {},
  is_shared: true,
  owner_user_id: 'uid-bob',
  owner_username: 'bob',
  created_at: '2026-05-26T10:00:00Z',
  updated_at: '2026-05-26T10:00:00Z',
}

// Legacy fixtures for Plan 21 tests (no owner fields needed for those tests)
const sampleTemplates: CommandTemplate[] = [
  {
    id: 't1',
    name: 'Web dry-run',
    description: 'Dry-run on web-*',
    target: 'web-*',
    target_type: 'glob',
    fun: 'state.highstate',
    args: [],
    kwargs: { test: 'True' },
    is_shared: false,
    owner_user_id: 'uid-alice',
    owner_username: 'alice',
    created_at: '2026-05-26T10:00:00Z',
    updated_at: '2026-05-26T10:00:00Z',
  },
]

// ─── MSW server ──────────────────────────────────────────────────────────────

let lastPatchBody: unknown = null

const server = setupServer(
  http.get('/api/auth/me', () => HttpResponse.json(ALICE_ME)),
  http.get('/api/templates', () =>
    HttpResponse.json({ total: 1, templates: sampleTemplates }),
  ),
  http.delete('/api/templates/:id', () => new HttpResponse(null, { status: 204 })),
  http.patch('/api/templates/:id', async ({ request, params }) => {
    lastPatchBody = await request.json()
    const id = params.id as string
    // Return a minimal updated template
    const base = [aliceTemplate, bobTemplate].find((t) => t.id === id) ?? aliceTemplate
    return HttpResponse.json({ ...base, ...(lastPatchBody as object) })
  }),
)

beforeAll(() => server.listen())
afterEach(() => {
  server.resetHandlers()
  lastPatchBody = null
})
afterAll(() => server.close())

// ─── helpers ─────────────────────────────────────────────────────────────────

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

// ─── Plan 21 tests ───────────────────────────────────────────────────────────

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

  // ─── Plan 22 smoke tests ──────────────────────────────────────────────────

  it('shows "Shared by bob" for a template not owned by the current user', async () => {
    server.use(
      http.get('/api/templates', () =>
        HttpResponse.json({ total: 1, templates: [bobTemplate] }),
      ),
    )
    const user = userEvent.setup()
    renderPicker()
    // Open the Select dropdown
    await user.click(await screen.findByRole('combobox'))
    expect(await screen.findByText('Shared by bob')).toBeInTheDocument()
  })

  it('ManageTemplatesDialog: own template gets a Switch, foreign template shows "Shared by bob"', async () => {
    server.use(
      http.get('/api/templates', () =>
        HttpResponse.json({ total: 2, templates: [aliceTemplate, bobTemplate] }),
      ),
    )
    const user = userEvent.setup()
    renderPicker()
    // Wait for the Manage button to appear (templates loaded)
    const manageBtn = await screen.findByRole('button', { name: /manage templates/i })
    await user.click(manageBtn)
    // Alice's row has a Switch (she owns it)
    expect(screen.getAllByRole('switch').length).toBeGreaterThanOrEqual(1)
    // Bob's row shows the "Shared by bob" badge
    expect(screen.getByText('Shared by bob')).toBeInTheDocument()
  })

  it('ManageTemplatesDialog: toggling the Switch fires PATCH with is_shared payload', async () => {
    server.use(
      http.get('/api/templates', () =>
        HttpResponse.json({ total: 2, templates: [aliceTemplate, bobTemplate] }),
      ),
    )
    const user = userEvent.setup()
    renderPicker()
    const manageBtn = await screen.findByRole('button', { name: /manage templates/i })
    await user.click(manageBtn)
    // Find alice's share switch (aria-label "Share Alice template")
    const shareSwitch = await screen.findByRole('switch', { name: /share alice template/i })
    await user.click(shareSwitch)
    await waitFor(() => {
      expect(lastPatchBody).toMatchObject({ is_shared: true })
    })
  })
})

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { RolePermissionsDialog } from '@/features/roles/role-permissions-dialog'

const role = {
  id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  name: 'operator',
  description: '',
  is_builtin: false,
  permissions: [
    { id: 'p1', verb: 'view', resource_glob: 'minion:*' },
    { id: 'p2', verb: 'run', resource_glob: 'state.*' },
  ],
}

let lastAdd: Record<string, unknown> | null = null
const removedPermissionIds: string[] = []

const server = setupServer(
  http.get(`/api/roles/${role.id}`, () => HttpResponse.json(role)),
  http.post(`/api/roles/${role.id}/permissions`, async ({ request }) => {
    lastAdd = (await request.json()) as Record<string, unknown>
    return HttpResponse.json(
      { id: 'p-new', verb: lastAdd.verb, resource_glob: lastAdd.resource_glob },
      { status: 201 },
    )
  }),
  http.delete(`/api/roles/${role.id}/permissions/:permissionId`, ({ params }) => {
    removedPermissionIds.push(String(params.permissionId))
    return new HttpResponse(null, { status: 204 })
  }),
)

beforeAll(() => server.listen())
afterEach(() => {
  server.resetHandlers()
  lastAdd = null
  removedPermissionIds.length = 0
})
afterAll(() => server.close())

function renderDialog() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <RolePermissionsDialog role={role} open onOpenChange={() => {}} />
    </QueryClientProvider>,
  )
}

describe('RolePermissionsDialog', () => {
  it('renders the current permissions', async () => {
    renderDialog()
    expect(await screen.findByText('view')).toBeInTheDocument()
    expect(screen.getByText('minion:*')).toBeInTheDocument()
    expect(screen.getByText('run')).toBeInTheDocument()
    // 'state.*' appears in both the description code block and the permission row
    expect(screen.getAllByText('state.*').length).toBeGreaterThanOrEqual(1)
  })

  it('adds a permission', async () => {
    const user = userEvent.setup()
    renderDialog()
    await screen.findByText('view')
    await user.type(screen.getByLabelText(/verb/i), 'accept')
    await user.type(screen.getByLabelText(/resource pattern/i), 'key:web-*')
    await user.click(screen.getByRole('button', { name: /add permission/i }))
    await waitFor(() => {
      expect(lastAdd).toEqual({ verb: 'accept', resource_glob: 'key:web-*' })
    })
  })

  it('removes a permission', async () => {
    const user = userEvent.setup()
    renderDialog()
    const btn = await screen.findByRole('button', { name: /remove view minion:\*/i })
    await user.click(btn)
    await waitFor(() => {
      expect(removedPermissionIds).toEqual(['p1'])
    })
  })
})

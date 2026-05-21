import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { ThemeProvider } from '@/app/theme/theme-provider'
import { UserMenu } from '@/app/layout/UserMenu'

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin',
      display_name: 'admin',
      must_change_pw: false,
      permissions: [],
    }),
  ),
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

beforeEach(() => {
  localStorage.removeItem('halite-theme')
  document.documentElement.classList.remove('dark')
})

function renderMenu() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const rootRoute = createRootRoute({ component: Outlet })
  const homeRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    component: () => <UserMenu />,
  })
  const router = createRouter({ routeTree: rootRoute.addChildren([homeRoute]) })
  return render(
    <QueryClientProvider client={qc}>
      <ThemeProvider>
        <RouterProvider router={router} />
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

describe('Theme toggle', () => {
  it('adds the dark class when Dark is chosen', async () => {
    const user = userEvent.setup()
    renderMenu()
    const trigger = await screen.findByRole('button', { name: /admin/i })
    await user.click(trigger)
    const themeItem = await screen.findByText(/^Theme$/)
    // ArrowRight opens the submenu in Radix UI's jsdom environment
    fireEvent.keyDown(themeItem, { key: 'ArrowRight' })
    await user.click(await screen.findByText(/^Dark/))
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('halite-theme')).toBe('dark')
  })

  it('removes the dark class when Light is chosen', async () => {
    document.documentElement.classList.add('dark')
    localStorage.setItem('halite-theme', 'dark')

    const user = userEvent.setup()
    renderMenu()
    const trigger = await screen.findByRole('button', { name: /admin/i })
    await user.click(trigger)
    const themeItem = await screen.findByText(/^Theme$/)
    // ArrowRight opens the submenu in Radix UI's jsdom environment
    fireEvent.keyDown(themeItem, { key: 'ArrowRight' })
    await user.click(await screen.findByText(/^Light/))
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem('halite-theme')).toBe('light')
  })
})

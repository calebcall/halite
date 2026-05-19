import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'

import { LoginPage } from '@/features/auth/login-page'
import { LoginRequired, PublicOnly } from '@/features/auth/guards'
import { AppShell } from './layout/AppShell'

const rootRoute = createRootRoute({ component: Outlet })

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: () => (
    <PublicOnly>
      <LoginPage />
    </PublicOnly>
  ),
})

const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'app',
  component: () => (
    <LoginRequired>
      <AppShell />
    </LoginRequired>
  ),
})

const homeRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/',
  component: () => (
    <div className="prose">
      <h2 className="text-xl font-semibold">Welcome to Halite</h2>
      <p className="text-muted-foreground">
        Feature pages arrive in subsequent plans. For now this is a working app shell on top of
        Plan&nbsp;1+2&apos;s backend.
      </p>
    </div>
  ),
})

const routeTree = rootRoute.addChildren([loginRoute, appRoute.addChildren([homeRoute])])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

export function AppRouter() {
  return <RouterProvider router={router} />
}

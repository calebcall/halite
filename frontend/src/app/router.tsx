import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'

import { LoginPage } from '@/features/auth/login-page'
import { ChangePasswordPage } from '@/features/auth/change-password-page'
import { LoginRequired, MustChangePassword, PublicOnly } from '@/features/auth/guards'
import { AuditViewerPage } from '@/features/audit/audit-viewer-page'
import { KeysListPage } from '@/features/keys/keys-list-page'
import { MinionDetailPage } from '@/features/minions/minion-detail-page'
import { MinionsListPage } from '@/features/minions/minions-list-page'
import { RolesListPage } from '@/features/roles/roles-list-page'
import { UsersListPage } from '@/features/users/users-list-page'
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

const changePasswordRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/change-password',
  component: () => <ChangePasswordPage />,
})

const homeRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/',
  component: () => (
    <MustChangePassword>
      <div className="prose">
        <h2 className="text-xl font-semibold">Welcome to Halite</h2>
        <p className="text-muted-foreground">
          Feature pages arrive in subsequent plans. For now this is a working app shell on top of
          Plan&nbsp;1+2&apos;s backend.
        </p>
      </div>
    </MustChangePassword>
  ),
})

const minionsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/minions',
  component: () => <MinionsListPage />,
})

const minionDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/minions/$minionId',
  component: () => <MinionDetailPage />,
})

const keysRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/keys',
  component: () => <KeysListPage />,
})

const usersRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/users',
  component: () => <UsersListPage />,
})

const rolesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/roles',
  component: () => <RolesListPage />,
})

const auditRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/audit',
  component: () => <AuditViewerPage />,
})

const routeTree = rootRoute.addChildren([
  loginRoute,
  appRoute.addChildren([
    changePasswordRoute,
    homeRoute,
    minionsRoute,
    minionDetailRoute,
    keysRoute,
    usersRoute,
    rolesRoute,
    auditRoute,
  ]),
])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

export function AppRouter() {
  return <RouterProvider router={router} />
}

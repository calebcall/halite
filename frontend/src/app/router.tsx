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
import { AboutPage } from '@/features/about/about-page'
import { AuditViewerPage } from '@/features/audit/audit-viewer-page'
import { InventoryPackagesPage } from '@/features/inventory/inventory-packages-page'
import { JobDetailPage } from '@/features/jobs/job-detail-page'
import { JobsListPage } from '@/features/jobs/jobs-list-page'
import { TimelinePage } from '@/features/jobs/timeline-page'
import { KeysListPage } from '@/features/keys/keys-list-page'
import { MinionDetailPage } from '@/features/minions/minion-detail-page'
import { MinionsListPage } from '@/features/minions/minions-list-page'
import { OverviewPage } from '@/features/overview/overview-page'
import { RolesListPage } from '@/features/roles/roles-list-page'
import { RunCommandPage } from '@/features/run/run-command-page'
import { SettingsPage } from '@/features/admin/settings-page'
import { SetupGuard } from '@/features/setup/setup-guard'
import { SetupWizardPage } from '@/features/setup/setup-wizard-page'
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
      <SetupGuard>
        <AppShell />
      </SetupGuard>
    </LoginRequired>
  ),
})

const changePasswordRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/change-password',
  component: () => <ChangePasswordPage />,
})

const setupRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/setup',
  component: () => (
    <MustChangePassword>
      <SetupWizardPage />
    </MustChangePassword>
  ),
})

const homeRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/',
  component: () => (
    <MustChangePassword>
      <OverviewPage />
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

const jobsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/jobs',
  component: () => <JobsListPage />,
})

const jobsTimelineRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/jobs/timeline',
  component: () => <TimelinePage />,
})

const jobDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/jobs/$jid',
  component: () => <JobDetailPage />,
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

type RunSearch = {
  target?: string
  target_type?: string
  fun?: string
  args?: string  // JSON-stringified array
  kwargs?: string  // JSON-stringified object
}

const runRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/run',
  validateSearch: (search: Record<string, unknown>): RunSearch => ({
    target: typeof search.target === 'string' ? search.target : undefined,
    target_type: typeof search.target_type === 'string' ? search.target_type : undefined,
    fun: typeof search.fun === 'string' ? search.fun : undefined,
    args: typeof search.args === 'string' ? search.args : undefined,
    kwargs: typeof search.kwargs === 'string' ? search.kwargs : undefined,
  }),
  component: () => <RunCommandPage />,
})

const auditRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/audit',
  component: () => <AuditViewerPage />,
})

const settingsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/admin/settings',
  component: () => <SettingsPage />,
})

const aboutRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/about',
  component: () => <AboutPage />,
})

// Inventory state lives in the URL — three drill-down levels controlled
// by which of (name, version, minion) are set.
type InventorySearch = {
  minion?: string
  name?: string
  version?: string
}

const inventoryRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/inventory',
  validateSearch: (search: Record<string, unknown>): InventorySearch => ({
    minion: typeof search.minion === 'string' ? search.minion : undefined,
    name: typeof search.name === 'string' ? search.name : undefined,
    version: typeof search.version === 'string' ? search.version : undefined,
  }),
  component: () => <InventoryPackagesPage />,
})

const routeTree = rootRoute.addChildren([
  loginRoute,
  appRoute.addChildren([
    changePasswordRoute,
    setupRoute,
    homeRoute,
    minionsRoute,
    minionDetailRoute,
    keysRoute,
    jobsRoute,
    jobsTimelineRoute,
    jobDetailRoute,
    inventoryRoute,
    usersRoute,
    rolesRoute,
    runRoute,
    auditRoute,
    settingsRoute,
    aboutRoute,
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

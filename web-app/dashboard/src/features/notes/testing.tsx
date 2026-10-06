import { render } from '@testing-library/react'
import type { RouteObject } from 'react-router'
import { RouterProvider, createMemoryRouter } from 'react-router'
import { ApiProvider } from '@/api/ApiProvider'
import type { ApiClient } from '@/api/client'
import { ToastProvider } from '@/components/Toast'
import { ClockProvider, fixedClock } from '@/lib/clock'
import { mockClient, TODAY } from '@/test/helpers'
import { setViewport } from '@/test/viewport'

/** Test helper for the notes and tasks packages: routes in the usual providers, at a given window width (`@/test/viewport`). */
export function renderRoutes(routes: RouteObject[], url: string, client: ApiClient = mockClient(), width = 1440) {
  setViewport(width)
  const router = createMemoryRouter(routes, { initialEntries: [url] })
  const view = render(
    <ApiProvider client={client}>
      <ClockProvider clock={fixedClock(TODAY)}>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </ClockProvider>
    </ApiProvider>,
  )
  return { router, ...view }
}

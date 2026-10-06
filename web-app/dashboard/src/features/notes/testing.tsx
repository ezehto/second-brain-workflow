import { render } from '@testing-library/react'
import { act } from '@testing-library/react'
import type { RouteObject } from 'react-router'
import { RouterProvider, createMemoryRouter } from 'react-router'
import { ApiProvider } from '@/api/ApiProvider'
import type { ApiClient } from '@/api/client'
import { ToastProvider } from '@/components/Toast'
import { ClockProvider, fixedClock } from '@/lib/clock'
import { mockClient, TODAY } from '@/test/helpers'

/** Test helpers for the notes and tasks packages: a window of a given width, and routes in the usual providers. */
const listeners = new Set<() => void>()

/** Makes `matchMedia` answer `(min-width: Npx)` queries for a window `width` wide. */
export function setWidth(width: number) {
  window.innerWidth = width
  window.matchMedia = ((query: string) => {
    const min = /\(min-width:\s*(\d+)px\)/.exec(query)
    return {
      get matches() {
        return !min || window.innerWidth >= Number(min[1])
      },
      media: query,
      addEventListener: (_: string, l: () => void) => listeners.add(l),
      removeEventListener: (_: string, l: () => void) => listeners.delete(l),
    } as unknown as MediaQueryList
  }) as typeof window.matchMedia
  act(() => listeners.forEach((l) => l()))
}

export function renderRoutes(routes: RouteObject[], url: string, client: ApiClient = mockClient(), width = 1440) {
  setWidth(width)
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

import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, createMemoryRouter } from 'react-router'
import { vi } from 'vitest'
import { App } from '@/App'
import { ApiProvider } from '@/api/ApiProvider'
import type { ApiClient } from '@/api/client'
import { createMockClient, type MockClientOptions } from '@/api/mock/mockClient'
import type { Query } from '@/api/useQuery'
import { ToastProvider } from '@/components/Toast'
import { ClockProvider, fixedClock } from '@/lib/clock'
import { createRoutes } from '@/routes'

export const TODAY = '2026-10-06'

export const ok = <T,>(data: T): Query<T> => ({ status: 'success', data, error: undefined, refetch: vi.fn() })
export const loading = <T,>(): Query<T> => ({ status: 'loading', data: undefined, error: undefined, refetch: vi.fn() })
export const failed = <T,>(message: string): Query<T> => ({ status: 'error', data: undefined, error: new Error(message), refetch: vi.fn() })

export const mockClient = (options: MockClientOptions = {}) => createMockClient({ delayMs: 0, today: TODAY, ...options })

/** A single component inside the providers it may use (router, clock, API, toast). */
export function renderInApp(ui: ReactElement, client: ApiClient = mockClient(), today = TODAY, url = '/') {
  return render(
    <ApiProvider client={client}>
      <ClockProvider clock={fixedClock(today)}>
        <ToastProvider>
          <MemoryRouter initialEntries={[url]}>{ui}</MemoryRouter>
        </ToastProvider>
      </ClockProvider>
    </ApiProvider>,
  )
}

/** The whole app at a route, on the mock API with no delay. */
export function renderApp(path = '/', client: ApiClient = mockClient(), today = TODAY) {
  const router = createMemoryRouter(createRoutes({ sampleData: true }), { initialEntries: [path] })
  return render(<App client={client} clock={fixedClock(today)} router={router} />)
}

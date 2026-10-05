import { RouterProvider, type createBrowserRouter } from 'react-router'
import { ApiProvider } from '@/api/ApiProvider'
import type { ApiClient } from '@/api/client'
import { ToastProvider } from '@/components/Toast'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ClockProvider, type Clock } from '@/lib/clock'

/** Providers and the router. Everything environmental (client, clock, router) is injected. */
export function App({ client, clock, router }: { client: ApiClient; clock: Clock; router: ReturnType<typeof createBrowserRouter> }) {
  return (
    <ApiProvider client={client}>
      <ClockProvider clock={clock}>
        <TooltipProvider>
          <ToastProvider>
            <RouterProvider router={router} />
          </ToastProvider>
        </TooltipProvider>
      </ClockProvider>
    </ApiProvider>
  )
}

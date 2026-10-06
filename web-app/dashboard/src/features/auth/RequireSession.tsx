import { Navigate, Outlet, useLocation } from 'react-router'
import { Button } from '@/components/ui/button'
import { routes } from '@/lib/routes'
import { loginHref } from './next'
import { useSession } from './SessionProvider'

/** Wraps every page but the login: signed out goes to `/login?next=…`, signed in renders the page. */
export function RequireSession() {
  const { state, retry } = useSession()
  const location = useLocation()

  if (state.status === 'unauthenticated') return <Navigate to={state.signedOut ? routes.login : loginHref(location)} replace />
  if (state.status === 'unavailable') {
    return (
      <div role="alert" className="mx-auto flex min-h-screen max-w-md flex-col items-start justify-center gap-3 px-6">
        <p className="m-0 font-medium text-status-blocked">Could not reach the dashboard server. {state.message}</p>
        <Button variant="secondary" onClick={retry}>
          Try again
        </Button>
      </div>
    )
  }
  if (state.status === 'loading') return <div role="status" aria-label="Checking your session" className="min-h-screen" />
  return <Outlet />
}

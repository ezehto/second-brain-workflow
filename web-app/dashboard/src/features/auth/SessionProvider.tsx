import { Outlet } from 'react-router'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useApi } from '@/api/ApiProvider'
import { ApiError } from '@/api/client'

/**
 * Who is signed in. `loading` until `me` answers; `unauthenticated` after a 401/403, a failed
 * `me`, or sign-out. The username is the only thing the session holds.
 */
export type SessionState =
  | { status: 'loading' }
  | { status: 'authenticated'; username: string }
  /** `signedOut`: the person chose to leave, so the login page does not send them back to where they were. */
  | { status: 'unauthenticated'; signedOut?: boolean }
  /** `me` failed for a reason other than "not signed in" (server down): do not send the person to a login that cannot work. */
  | { status: 'unavailable'; message: string }

export interface Session {
  state: SessionState
  /** Rejects with the API's `ApiError` (wrong password, throttled, CSRF). */
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  retry: () => void
}

const SessionContext = createContext<Session | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const client = useApi()
  const [state, setState] = useState<SessionState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => client.onUnauthenticated(() => setState({ status: 'unauthenticated' })), [client])

  useEffect(() => {
    let current = true
    client.me().then(
      (me) => current && setState({ status: 'authenticated', username: me.username }),
      (error: unknown) => {
        if (!current) return
        const signedOut = error instanceof ApiError && (error.status === 401 || error.status === 403)
        setState(signedOut ? { status: 'unauthenticated' } : { status: 'unavailable', message: error instanceof Error ? error.message : String(error) })
      },
    )
    return () => {
      current = false
    }
  }, [client, attempt])

  const login = useCallback(
    async (username: string, password: string) => {
      const me = await client.login({ username, password })
      setState({ status: 'authenticated', username: me.username })
    },
    [client],
  )
  const logout = useCallback(async () => {
    try {
      await client.logout()
    } finally {
      // Whatever the server said, this browser no longer treats the person as signed in.
      setState({ status: 'unauthenticated', signedOut: true })
    }
  }, [client])
  const retry = useCallback(() => {
    setState({ status: 'loading' })
    setAttempt((n) => n + 1)
  }, [])

  const value = useMemo(() => ({ state, login, logout, retry }), [state, login, logout, retry])
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): Session {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used inside <SessionProvider>')
  return ctx
}

/** Route element that gives every route below it the session. */
export function SessionLayout() {
  return (
    <SessionProvider>
      <Outlet />
    </SessionProvider>
  )
}

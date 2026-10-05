import { useCallback, useEffect, useRef, useState } from 'react'
import { useApiVersion } from './ApiProvider'

export type QueryState<T> =
  | { status: 'loading'; data: undefined; error: undefined }
  | { status: 'error'; data: undefined; error: Error }
  | { status: 'success'; data: T; error: undefined }

export type Query<T> = QueryState<T> & { refetch: () => void }

const LOADING = { status: 'loading', data: undefined, error: undefined } as const

/**
 * Runs `fetcher` on mount and again when the API version changes (a write
 * succeeded somewhere) or `refetch` is called. A late response from an older
 * run is dropped. Pass a stable `fetcher` (wrap it in useCallback).
 *
 * A new `fetcher` is a new question (another route param or filter): the
 * result is `loading` until it answers, never the previous question's data.
 * An invalidate or `refetch` re-asks the same question, so the data on screen
 * is kept until the new answer arrives.
 */
export function useQuery<T>(fetcher: () => Promise<T>): Query<T> {
  const version = useApiVersion()
  const [answer, setAnswer] = useState<{ fetcher: () => Promise<T>; state: QueryState<T> }>({ fetcher, state: LOADING })
  const [manual, setManual] = useState(0)
  const run = useRef(0)

  useEffect(() => {
    const id = ++run.current
    fetcher().then(
      (data) => {
        if (id === run.current) setAnswer({ fetcher, state: { status: 'success', data, error: undefined } })
      },
      (error: unknown) => {
        if (id === run.current) setAnswer({ fetcher, state: { status: 'error', data: undefined, error: error instanceof Error ? error : new Error(String(error)) } })
      },
    )
    return () => {
      run.current += 1
    }
  }, [fetcher, version, manual])

  const refetch = useCallback(() => {
    setAnswer((a) => (a.state.status === 'error' ? { ...a, state: LOADING } : a))
    setManual((n) => n + 1)
  }, [])

  const state: QueryState<T> = answer.fetcher === fetcher ? answer.state : LOADING
  return { ...state, refetch }
}

/** One query out of two: loading until both load, an error if either fails. */
export function joinQueries<A, B>(a: Query<A>, b: Query<B>): Query<[A, B]> {
  const refetch = () => {
    if (a.status === 'error') a.refetch()
    if (b.status === 'error') b.refetch()
  }
  if (a.status === 'error') return { status: 'error', data: undefined, error: a.error, refetch }
  if (b.status === 'error') return { status: 'error', data: undefined, error: b.error, refetch }
  if (a.status === 'loading' || b.status === 'loading') return { status: 'loading', data: undefined, error: undefined, refetch }
  return { status: 'success', data: [a.data, b.data], error: undefined, refetch }
}

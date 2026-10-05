import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import type { ApiClient } from './client'
import { createHttpClient } from './http'
import { createMockClient } from './mock/mockClient'

export type ApiMode = 'mock' | 'http'

/** Reads `VITE_API_MODE`; anything but `http` is the mock. */
export function resolveApiMode(value: string | undefined): ApiMode {
  return value === 'http' ? 'http' : 'mock'
}

/** `today` pins the mock's date; the caller gives the same value to the clock. */
export function createApiClient(mode: ApiMode, options: { today?: string } = {}): ApiClient {
  return mode === 'http' ? createHttpClient() : createMockClient({ today: options.today })
}

interface ApiContextValue {
  client: ApiClient
  /** Increases after every successful write; queries refetch when it does. */
  version: number
  invalidate: () => void
}

const ApiContext = createContext<ApiContextValue | null>(null)

export function ApiProvider({ client, children }: { client: ApiClient; children: ReactNode }) {
  const [version, setVersion] = useState(0)
  const invalidate = useCallback(() => setVersion((v) => v + 1), [])
  const value = useMemo(() => ({ client, version, invalidate }), [client, version, invalidate])
  return <ApiContext.Provider value={value}>{children}</ApiContext.Provider>
}

function useApiContext(): ApiContextValue {
  const ctx = useContext(ApiContext)
  if (!ctx) throw new Error('useApi must be used inside <ApiProvider>')
  return ctx
}

export const useApi = (): ApiClient => useApiContext().client
export const useApiVersion = (): number => useApiContext().version
/** Call after a successful write so every mounted query refetches. */
export const useInvalidate = (): (() => void) => useApiContext().invalidate

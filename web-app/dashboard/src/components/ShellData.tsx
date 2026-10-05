import { createContext, useContext } from 'react'
import type { DashboardResponse } from '@/api/types'
import type { Query } from '@/api/useQuery'

/**
 * The dashboard aggregate, fetched once by the shell. The shell needs it for
 * the vault's "today"; the Dashboard page reads the same query so the two can
 * never disagree.
 */
export const ShellDashboardContext = createContext<Query<DashboardResponse> | null>(null)

export function useShellDashboard(): Query<DashboardResponse> {
  const query = useContext(ShellDashboardContext)
  if (!query) throw new Error('useShellDashboard must be used inside <AppShell>')
  return query
}

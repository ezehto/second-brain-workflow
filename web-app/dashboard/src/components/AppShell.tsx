import { useCallback, useMemo, useState } from 'react'
import { Outlet } from 'react-router'
import { useApi } from '@/api/ApiProvider'
import { useQuery } from '@/api/useQuery'
import { ClockProvider, fixedClock, useClock } from '@/lib/clock'
import { routes } from '@/lib/routes'
import { hasTabBar, useViewport } from '@/lib/viewport'
import { cn } from '@/lib/utils'
import { indexProblemCount } from '@/domain/indexStatus'
import { ContextSelect } from './ContextSelect'
import { Header } from './Header'
import { LoadingRows } from './QueryBoundary'
import { PageTitleProvider } from './PageTitle'
import { QuickActionsProvider } from './QuickActions'
import { MobileTabBar, NavSheet } from './MobileTabBar'
import { Rail } from './Rail'
import { ShellDashboardContext } from './ShellData'

/**
 * The frame every page sits in: navigation, top bar, the page outlet, and the
 * creation dialogs. Navigation depends on width (see `useViewport`): a labelled
 * rail, an icon rail, or a bottom tab bar. The content area is at most 1840px
 * wide with a 24px gutter (16px on a phone) so pages can use three columns.
 *
 * The shell is also the single source of "today". It asks the server (the
 * dashboard aggregate, then the index status' test-mode date) and provides
 * that date through `ClockProvider`, because the server's counts and rules use
 * the vault's date, which the backend test clock can pin (plan 2.12). The
 * injected clock is only the fallback if the server cannot answer. Pages are
 * not rendered until the date is known, so nothing paints with a wrong day.
 */
export function AppShell({ sampleData }: { sampleData: boolean }) {
  const client = useApi()
  const fallbackClock = useClock()
  const viewport = useViewport()
  const [menu, setMenu] = useState(false)
  // The menu belongs to one layout: a resize to another starts closed.
  const [menuViewport, setMenuViewport] = useState(viewport)
  if (menuViewport !== viewport) {
    setMenuViewport(viewport)
    setMenu(false)
  }

  const dashboard = useQuery(useCallback(() => client.getDashboard(), [client]))
  const index = useQuery(useCallback(() => client.getIndexStatus(), [client]))
  const inbox = useQuery(useCallback(() => client.listNotes({ type: 'capture', status: ['inbox'], page_size: 1 }), [client]))
  const blocked = useQuery(useCallback(() => client.listNotes({ type: 'task', status: ['blocked'], page_size: 1 }), [client]))

  const serverToday =
    dashboard.status === 'success' ? dashboard.data.today : index.status === 'success' ? index.data.test_mode?.today : undefined
  const clock = useMemo(() => (serverToday ? fixedClock(serverToday) : fallbackClock), [serverToday, fallbackClock])
  const todayKnown = dashboard.status !== 'loading'

  // Counts show only above zero: captures to triage, blocked tasks, index problems.
  const counts = {
    [routes.inbox]: inbox.status === 'success' ? inbox.data.count : undefined,
    [routes.tasks]: blocked.status === 'success' ? blocked.data.count : undefined,
    [routes.indexStatus]: index.status === 'success' ? indexProblemCount(index.data) : undefined,
  }

  const tabBar = hasTabBar(viewport)

  return (
    <ClockProvider clock={clock}>
      <ShellDashboardContext.Provider value={dashboard}>
        <QuickActionsProvider>
          <PageTitleProvider>
          <div className="flex min-h-screen">
            {(viewport === 'wide' || viewport === 'compact') && (
              <aside
                className={cn(
                  'sticky top-0 h-screen flex-none self-start overflow-y-auto border-r border-line bg-rail',
                  viewport === 'wide' ? 'w-56' : 'w-[4.5rem]',
                )}
              >
                <Rail variant={viewport === 'wide' ? 'full' : 'icon'} counts={counts} sampleData={sampleData} />
              </aside>
            )}

            <div className="flex min-w-0 flex-1 flex-col">
              <Header
                index={index.status === 'success' ? index.data : undefined}
                todayKnown={todayKnown}
                viewport={viewport}
                onOpenMenu={() => setMenu(true)}
              />
              <main className={cn('mx-auto flex w-full max-w-[1840px] flex-1 flex-col gap-4 px-4 pt-4 sm:px-6', tabBar ? 'pb-24' : 'pb-6')}>
                {todayKnown ? <Outlet /> : <LoadingRows rows={4} />}
              </main>
            </div>

            {tabBar && <MobileTabBar counts={counts} sampleData={sampleData} extra={viewport === 'phone' ? <ContextSelect className="w-full" /> : undefined} />}
            {viewport === 'tablet' && (
              <NavSheet open={menu} onOpenChange={setMenu} counts={counts} sampleData={sampleData} extra={<ContextSelect className="w-full" />} />
            )}
          </div>
          </PageTitleProvider>
        </QuickActionsProvider>
      </ShellDashboardContext.Provider>
    </ClockProvider>
  )
}

import { useCallback, useMemo, useState } from 'react'
import { Outlet } from 'react-router'
import { useApi } from '@/api/ApiProvider'
import { useQuery } from '@/api/useQuery'
import { ClockProvider, fixedClock, useClock } from '@/lib/clock'
import { routes } from '@/lib/routes'
import { indexProblemCount } from '@/domain/indexStatus'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Header } from './Header'
import { Icon } from './Icon'
import { LoadingRows } from './QueryBoundary'
import { Rail } from './Rail'
import { ShellDashboardContext } from './ShellData'

/**
 * The frame every page sits in: rail, header, and the page outlet. Below the
 * rail breakpoint the rail becomes a drawer opened from a top bar.
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
  const [drawer, setDrawer] = useState(false)

  const dashboard = useQuery(useCallback(() => client.getDashboard(), [client]))
  const index = useQuery(useCallback(() => client.getIndexStatus(), [client]))
  const inbox = useQuery(useCallback(() => client.listNotes({ type: 'capture', status: ['inbox'], page_size: 1 }), [client]))

  const serverToday =
    dashboard.status === 'success' ? dashboard.data.today : index.status === 'success' ? index.data.test_mode?.today : undefined
  const clock = useMemo(() => (serverToday ? fixedClock(serverToday) : fallbackClock), [serverToday, fallbackClock])
  const todayKnown = dashboard.status !== 'loading'

  const counts = {
    [routes.inbox]: inbox.status === 'success' ? inbox.data.count : undefined,
    [routes.indexStatus]: index.status === 'success' ? indexProblemCount(index.data) : undefined,
  }

  return (
    <ClockProvider clock={clock}>
      <ShellDashboardContext.Provider value={dashboard}>
        <div className="flex min-h-screen flex-col rail:flex-row">
          <aside className="sticky top-0 hidden h-screen w-60 flex-none self-start overflow-y-auto border-r border-line bg-rail rail:block">
            <Rail counts={counts} sampleData={sampleData} />
          </aside>

          <div className="flex items-center gap-3 border-b border-line bg-rail px-4 py-2.5 rail:hidden">
            <Button variant="secondary" size="icon" onClick={() => setDrawer(true)} aria-label="Open navigation">
              <Icon name="menu" className="size-5" />
            </Button>
            <span aria-hidden="true" className="size-[22px] rounded-[7px] bg-brand-fill" />
            <span className="text-[17px] font-extrabold">Second Brain</span>
          </div>
          <Dialog open={drawer} onOpenChange={setDrawer}>
            <DialogContent className="top-0 left-0 h-full max-h-none w-72 max-w-[85vw] translate-x-0 translate-y-0 content-start gap-0 overflow-y-auto rounded-none border-0 border-r bg-rail p-0 sm:max-w-[85vw] rail:hidden">
              <DialogTitle className="sr-only">Navigation</DialogTitle>
              <DialogDescription className="sr-only">Pages of the dashboard</DialogDescription>
              <Rail counts={counts} sampleData={sampleData} onNavigate={() => setDrawer(false)} />
            </DialogContent>
          </Dialog>

          <div className="flex min-w-0 flex-1 flex-col">
            <Header index={index.status === 'success' ? index.data : undefined} todayKnown={todayKnown} />
            <main className="flex w-full max-w-[1360px] flex-1 flex-col gap-5 px-4 pt-3 pb-7 rail:px-7">
              {todayKnown ? <Outlet /> : <LoadingRows rows={4} />}
            </main>
          </div>
        </div>
      </ShellDashboardContext.Provider>
    </ClockProvider>
  )
}

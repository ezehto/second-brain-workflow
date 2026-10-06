import { useState } from 'react'
import { NavLink } from 'react-router'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { useProjectContext, withProject } from '@/lib/projectContext'
import { cn } from '@/lib/utils'
import { Icon } from './Icon'
import { TAB_ITEMS } from './nav'
import { Rail, type RailCounts } from './Rail'

/**
 * Bottom navigation for phone and tablet widths: Today, Tasks, Standup,
 * Projects, and More, which opens a sheet with every other destination.
 * 56px high, with 44px-wide touch targets.
 */
export function MobileTabBar({ counts, sampleData, extra }: { counts: RailCounts; sampleData: boolean; extra?: React.ReactNode }) {
  const [more, setMore] = useState(false)
  const project = useProjectContext()
  return (
    <>
      <nav aria-label="Primary" className="fixed inset-x-0 bottom-0 z-40 flex h-14 border-t border-line bg-rail">
        {TAB_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={withProject(item.to, project)}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                'relative flex min-w-11 flex-1 flex-col items-center justify-center gap-0.5 t-caption font-semibold no-underline',
                isActive ? 'text-ink' : 'text-muted-ink hover:text-ink',
              )
            }
          >
            {({ isActive }) => (
              <>
                <span className={cn('flex h-6 w-10 items-center justify-center rounded-full', isActive && 'bg-brand-fill text-white')}>
                  <Icon name={item.icon} className="size-5" />
                </span>
                {item.label}
                {counts[item.to] ? (
                  <span className="num absolute top-1 right-[calc(50%-1.5rem)] min-w-4 rounded-full bg-line px-1 text-center t-caption leading-4 font-bold text-ink">
                    <span className="sr-only">Count: </span>
                    {counts[item.to]}
                  </span>
                ) : null}
              </>
            )}
          </NavLink>
        ))}
        <button
          type="button"
          onClick={() => setMore(true)}
          aria-haspopup="dialog"
          className="flex min-w-11 flex-1 cursor-pointer flex-col items-center justify-center gap-0.5 t-caption font-semibold text-muted-ink hover:text-ink"
        >
          <span className="flex h-6 w-10 items-center justify-center">
            <Icon name="dots" className="size-5" />
          </span>
          More
        </button>
      </nav>
      <NavSheet open={more} onOpenChange={setMore} counts={counts} sampleData={sampleData} restOnly extra={extra} />
    </>
  )
}

/** The navigation in a left sheet: everything (`restOnly` false) or what the tab bar lacks. */
export function NavSheet({
  open,
  onOpenChange,
  counts,
  sampleData,
  restOnly = false,
  extra,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  counts: RailCounts
  sampleData: boolean
  restOnly?: boolean
  extra?: React.ReactNode
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="top-0 left-0 h-full max-h-none w-72 max-w-[85vw] translate-x-0 translate-y-0 content-start gap-0 overflow-y-auto rounded-none border-0 border-r bg-rail p-0 sm:max-w-[85vw]">
        <DialogTitle className="sr-only">{restOnly ? 'More' : 'Navigation'}</DialogTitle>
        <DialogDescription className="sr-only">Pages of the dashboard</DialogDescription>
        {extra && <div className="border-b border-line p-3">{extra}</div>}
        <Rail variant="sheet" counts={counts} sampleData={sampleData} onNavigate={() => onOpenChange(false)} hideTabItems={restOnly} />
      </DialogContent>
    </Dialog>
  )
}

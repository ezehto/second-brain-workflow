import { useState } from 'react'
import { NavLink, useLocation } from 'react-router'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useProjectContext, withProject } from '@/lib/projectContext'
import { cn } from '@/lib/utils'
import { Icon } from './Icon'
import { NAV_GROUPS, TAB_ITEMS, type NavGroup, type NavItem } from './nav'

export interface RailCounts {
  /** Count chip per route, shown only when above zero. */
  [to: string]: number | undefined
}

export type RailVariant = 'full' | 'icon' | 'sheet'

const LATER_KEY = 'sb.rail.later'

function readLater(): boolean {
  try {
    return window.localStorage.getItem(LATER_KEY) === '1'
  } catch {
    return false
  }
}

/** Open state of the "Later" group, remembered in localStorage (and fine without it). */
function useLaterOpen(): [boolean, () => void] {
  const [open, setOpen] = useState(readLater)
  const toggle = () =>
    setOpen((was) => {
      try {
        window.localStorage.setItem(LATER_KEY, was ? '0' : '1')
      } catch {
        // Storage can be blocked; the group still opens for this visit.
      }
      return !was
    })
  return [open, toggle]
}

function groupsFor(variant: RailVariant, hideTabItems: boolean): NavGroup[] {
  if (variant !== 'sheet' || !hideTabItems) return NAV_GROUPS
  const inTabs = new Set(TAB_ITEMS.map((i) => i.to))
  return NAV_GROUPS.map((g) => ({ ...g, items: g.items.filter((i) => !inTabs.has(i.to)) })).filter((g) => g.items.length)
}

const LINK = 'flex items-center rounded-btn font-semibold no-underline'
const linkState = (isActive: boolean) => (isActive ? 'bg-brand-fill text-white hover:text-white' : 'text-muted-ink hover:bg-inset hover:text-ink')

function CountChip({ count, floating }: { count: number | undefined; floating?: boolean }) {
  if (!count) return null
  return (
    <span
      className={cn(
        'num t-caption rounded-full bg-inset px-1.5 font-bold text-ink',
        floating ? 'absolute -top-0.5 -right-0.5 min-w-4 border border-rail bg-line px-1 text-center leading-4' : 'ml-auto',
      )}
    >
      <span className="sr-only">Count: </span>
      {count}
    </span>
  )
}

/**
 * The navigation: product mark, groups and a note when the data is not real.
 * `full` is 224px with labels, `icon` is the 56px rail with tooltips, `sheet`
 * is the full list inside a drawer (with `hideTabItems`, only what the bottom
 * tab bar does not already hold). The "Later" group is collapsed until opened.
 * Links keep the project context in the query string.
 */
export function Rail({
  variant = 'full',
  counts = {},
  sampleData,
  onNavigate,
  hideTabItems = false,
}: {
  variant?: RailVariant
  counts?: RailCounts
  sampleData: boolean
  onNavigate?: () => void
  hideTabItems?: boolean
}) {
  const project = useProjectContext()
  const { pathname } = useLocation()
  const [laterOpen, toggleLater] = useLaterOpen()
  const compact = variant === 'icon'

  const linkTo = (item: NavItem) => withProject(item.to, project)
  const renderItem = (item: NavItem) => {
    const count = counts[item.to]
    if (compact) {
      return (
        <li key={item.to}>
          <Tooltip>
            {/* A wrapper is the trigger: Radix Slot cannot merge NavLink's className function. */}
            <TooltipTrigger asChild>
              <span className="mx-auto flex size-10">
                <NavLink
                  to={linkTo(item)}
                  end={item.to === '/'}
                  aria-label={item.label}
                  className={({ isActive }) => cn(LINK, 'relative size-10 justify-center', linkState(isActive))}
                >
                  <Icon name={item.icon} />
                  <CountChip count={count} floating />
                </NavLink>
              </span>
            </TooltipTrigger>
            <TooltipContent side="right">{item.label}</TooltipContent>
          </Tooltip>
        </li>
      )
    }
    return (
      <li key={item.to}>
        <NavLink
          to={linkTo(item)}
          end={item.to === '/'}
          onClick={onNavigate}
          className={({ isActive }) => cn(LINK, 'min-h-9 gap-2.5 px-3 t-body max-rail:min-h-11', linkState(isActive))}
        >
          <Icon name={item.icon} />
          <span>{item.label}</span>
          <CountChip count={count} />
        </NavLink>
      </li>
    )
  }

  return (
    <TooltipProvider delayDuration={100}>
      <nav aria-label="Main" className={cn('flex min-h-full flex-col', compact ? 'items-stretch gap-3 px-2 py-3' : 'gap-4 px-3 py-4')}>
        {compact ? (
          <span aria-hidden="true" className="mx-auto size-[22px] rounded-[7px] bg-brand-fill" />
        ) : (
          <div className="flex flex-col gap-1 px-3">
            <div className="flex items-center gap-2.5">
              <span aria-hidden="true" className="size-[22px] rounded-[7px] bg-brand-fill" />
              <span className="t-panel font-bold">Second Brain</span>
            </div>
            <div className="mono text-muted-ink">D:\Second Brain</div>
          </div>
        )}

        {groupsFor(variant, hideTabItems).map((group) => {
          const activeInGroup = group.items.some((i) => (i.to === '/' ? pathname === '/' : pathname.startsWith(i.to)))
          const open = !group.collapsible || laterOpen || activeInGroup
          return (
            <div key={group.label}>
              {group.collapsible ? (
                <button
                  type="button"
                  onClick={toggleLater}
                  aria-expanded={open}
                  aria-controls={`rail-group-${group.label}`}
                  aria-label={compact ? `${group.label} pages` : undefined}
                  className={cn(
                    'flex cursor-pointer items-center gap-1 rounded-btn text-muted-ink hover:text-ink',
                    compact ? 'mx-auto size-8 justify-center' : 'w-full px-3 pb-1 t-caption font-semibold text-faint hover:text-ink',
                  )}
                >
                  <Icon name="chevron" className={cn('size-3.5 transition-transform', open ? '' : '-rotate-90')} />
                  {!compact && group.label}
                </button>
              ) : compact ? (
                <div aria-hidden="true" className="mx-2 mb-2 h-px bg-line" />
              ) : (
                <div className="t-caption px-3 pb-1 font-semibold text-faint">{group.label}</div>
              )}
              {open && (
                <ul id={`rail-group-${group.label}`} className="m-0 flex list-none flex-col gap-0.5 p-0">
                  {group.items.map(renderItem)}
                </ul>
              )}
            </div>
          )
        })}

        {sampleData && !compact && <p className="note mt-auto mb-0 px-3">Sample data. This build runs on a mock API, not your vault.</p>}
        {sampleData && compact && (
          <p className="note mt-auto mb-0 text-center" title="Sample data. This build runs on a mock API, not your vault.">
            Mock
          </p>
        )}
      </nav>
    </TooltipProvider>
  )
}

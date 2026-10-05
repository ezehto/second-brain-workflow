import { NavLink } from 'react-router'
import { cn } from '@/lib/utils'
import { Icon } from './Icon'
import { NAV_GROUPS } from './nav'

export interface RailCounts {
  /** Count chip per route, e.g. captures awaiting triage on Inbox. */
  [to: string]: number | undefined
}

/** Product mark, the four nav groups, and a note when the data is not real. */
export function Rail({ counts = {}, sampleData, onNavigate }: { counts?: RailCounts; sampleData: boolean; onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="flex min-h-full flex-col gap-[18px] px-3.5 py-5">
      <div className="flex flex-col gap-1 px-3">
        <div className="flex items-center gap-2.5">
          <span aria-hidden="true" className="size-[22px] rounded-[7px] bg-brand-fill" />
          <span className="text-[17px] font-extrabold">Second Brain</span>
        </div>
        <div className="mono text-muted-ink">D:\Second Brain</div>
      </div>
      {NAV_GROUPS.map((group) => (
        <div key={group.label}>
          <div className="px-3 pb-1 text-xs font-semibold text-faint">{group.label}</div>
          <ul className="m-0 flex list-none flex-col gap-0.5 p-0">
            {group.items.map((item) => {
              const count = counts[item.to]
              return (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.to === '/'}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        'flex min-h-10 items-center gap-2.5 rounded-btn px-3 font-semibold no-underline max-rail:min-h-11',
                        isActive ? 'bg-brand-fill text-white hover:text-white' : 'text-muted-ink hover:bg-inset hover:text-ink',
                      )
                    }
                  >
                    <Icon name={item.icon} />
                    <span>{item.label}</span>
                    {item.preview && <span className="note ml-auto">Preview</span>}
                    {count ? (
                      <span className="num ml-auto rounded-full bg-inset px-2 py-px text-xs font-bold text-ink">
                        <span className="sr-only">Count: </span>
                        {count}
                      </span>
                    ) : null}
                  </NavLink>
                </li>
              )
            })}
          </ul>
        </div>
      ))}
      {sampleData && (
        <p className="note mt-auto mb-0 px-3">Sample data. This build runs on a mock API, not your vault.</p>
      )}
    </nav>
  )
}

import type { ReactNode } from 'react'
import { Link } from 'react-router'

export interface ActivityItem {
  key: string
  /** Time of day for today's entries, a short date otherwise. */
  when: string
  /** Type and source, e.g. `task, vault`. Literal vault text, shown in mono. */
  meta: string
  title: string
  href: string
}

/** Entries on a dotted rail, newest first. */
export function ActivityList({ items, empty }: { items: ActivityItem[]; empty?: ReactNode }) {
  if (!items.length) return <>{empty}</>
  return (
    <ol className="rail-list mx-5 mt-0 mb-3.5 list-none p-0 pl-[22px]">
      {items.map((item) => (
        <li key={item.key} className="relative pt-1 pb-2.5">
          <span className="rail-dot" aria-hidden="true" />
          <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
            <span className="num note">{item.when}</span>
            <span className="mono text-muted-ink">{item.meta}</span>
          </div>
          <Link to={item.href} className="linkbtn">
            {item.title}
          </Link>
        </li>
      ))}
    </ol>
  )
}

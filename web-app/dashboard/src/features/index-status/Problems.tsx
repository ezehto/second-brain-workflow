import { Link } from 'react-router'
import { INDEX_PROBLEM_CATEGORIES, type IndexStatus } from '@/api/types'
import { Card, CardHead, CardRow } from '@/components/Card'
import { indexProblemCount } from '@/domain/indexStatus'
import { noteHref } from '@/lib/routes'
import { CATEGORY_LABELS } from './categories'

/** Every problem category, with its count or "None" and the notes it affects. */
export function Problems({ status }: { status: IndexStatus }) {
  return (
    <Card>
      <CardHead title="Problems by category" count={indexProblemCount(status)} />
      <ul className="m-0 list-none p-0">
        {INDEX_PROBLEM_CATEGORIES.map((key) => {
          const items = status.problems[key] ?? []
          const label = CATEGORY_LABELS[key]
          return (
            <li key={key} aria-label={label}>
              <CardRow className="min-h-8 grid-cols-[minmax(0,1fr)_auto]">
                <h3 className="t-body m-0 font-semibold">{label}</h3>
                <span className={items.length ? 'num font-semibold text-status-blocked' : 'text-muted-ink'}>
                  {items.length ? `${items.length} ${items.length === 1 ? 'note' : 'notes'}` : 'None'}
                </span>
              </CardRow>
              {items.length > 0 && (
                <ul className="m-0 list-none p-0">
                  {items.map((p) => (
                    <li key={`${p.path}|${p.detail}`} className="flex min-w-0 flex-col px-3 pb-2">
                      <Link to={noteHref(p.path)} className="t-small min-w-0 font-mono break-words">
                        {p.path}
                      </Link>
                      <span className="t-small text-muted-ink">{p.detail}</span>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

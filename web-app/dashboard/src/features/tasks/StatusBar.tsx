import { TASK_STATUSES } from '@/api/types'
import { Card, CardHead } from '@/components/Card'
import { TASK_SEGMENT_COLOR } from '@/domain/status'
import { cn } from '@/lib/utils'

const BUTTON =
  'flex min-w-24 cursor-pointer flex-col gap-1 rounded-btn border bg-transparent px-2 py-1 text-left hover:bg-inset max-rail:min-h-11'

/**
 * "Where do my tasks stand?" The status distribution as one bar of seven
 * segments, each as long as its share and each a filter button with its count
 * in text. "Open" and "All" sit beside it. Counts follow the other filters
 * (project, priority, overdue, today) but not the status filter itself.
 */
export function StatusBar({
  counts,
  open,
  total,
  value,
  onChange,
}: {
  counts: Record<string, number>
  open: number
  total: number
  /** The current status filter: a status, `open`, or undefined for all. */
  value: string | undefined
  onChange: (status: string | undefined) => void
}) {
  const pill = (label: string, count: number, on: boolean, next: string | undefined) => (
    <button
      key={label}
      type="button"
      aria-pressed={on}
      onClick={() => onChange(next)}
      className={cn(BUTTON, 'flex-none justify-end', on ? 'border-brand bg-inset' : 'border-transparent')}
    >
      <span aria-hidden="true" className="h-1.5 w-full rounded-full bg-line" />
      <span className="t-small font-semibold">
        {label} <span className="num">{count}</span>
      </span>
    </button>
  )

  return (
    <Card>
      <CardHead title="Where tasks stand" count={total} />
      <div role="group" aria-label="Filter by status" className="flex flex-wrap items-stretch gap-1 px-3 pb-3">
        {pill('Open', open, value === 'open', 'open')}
        {pill('All', total, value === undefined, undefined)}
        <span aria-hidden="true" className="mx-1 w-px self-stretch bg-line" />
        {TASK_STATUSES.map((status) => {
          const count = counts[status] ?? 0
          const on = value === status
          return (
            <button
              key={status}
              type="button"
              aria-pressed={on}
              onClick={() => onChange(status)}
              style={{ flexGrow: count }}
              className={cn(BUTTON, on ? 'border-brand bg-inset' : 'border-transparent')}
            >
              <span aria-hidden="true" className={cn('h-1.5 w-full rounded-full', count === 0 && 'opacity-30')} style={{ background: TASK_SEGMENT_COLOR[status] }} />
              <span className={cn('t-small font-semibold', count === 0 && 'text-muted-ink')}>
                {status} <span className="num">{count}</span>
              </span>
            </button>
          )
        })}
      </div>
    </Card>
  )
}

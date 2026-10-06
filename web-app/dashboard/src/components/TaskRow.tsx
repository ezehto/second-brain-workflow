import type { ReactNode } from 'react'
import { Link } from 'react-router'
import type { NoteSummary } from '@/api/types'
import { isOverdue } from '@/domain/tasks'
import { useToday } from '@/lib/clock'
import { formatShortDate } from '@/lib/dates'
import { useProjectHref } from '@/lib/projectContext'
import { cn } from '@/lib/utils'
import { CardRow } from './Card'
import { PriorityMark } from './PriorityMark'
import { StatusChip } from './StatusChip'

/**
 * One task as a row of a panel, shared by Today, Tasks, Project and Search:
 * priority mark, title (a link to the note), project, and a status slot.
 *
 * Without `reason` it is a 36px single line: the project and the due date sit
 * on the same line, and an overdue date says "Overdue" as well as turning red.
 * With `reason` (why the task is here, e.g. "Blocked: staging refresh") it is a
 * 48px two-line row, with the reason and project under the title.
 *
 * Below the `sm` breakpoint a one-line, non-dense row wraps its title to two
 * lines (a 48px row) instead of cutting it off.
 *
 * `status` defaults to a read-only chip; pass a `StatusMenu` to make it editable.
 *
 * `dense` makes a one-line row 32px (dense tables; the status control must fit
 * in 32px). `onOpen` lets a page open the note in a split pane instead of
 * navigating: a plain click on the title calls it, a modified click still
 * follows the link. `selected` marks the row whose note is open.
 */
export function TaskRow({
  task,
  project,
  reason,
  status,
  dense,
  selected,
  onOpen,
}: {
  task: NoteSummary
  /** Display name of the task's project, already resolved. */
  project?: string
  reason?: ReactNode
  status?: ReactNode
  dense?: boolean
  selected?: boolean
  onOpen?: (task: NoteSummary) => void
}) {
  const today = useToday()
  const href = useProjectHref()
  const overdue = isOverdue(task, today)
  // A one-line row may wrap its title to two lines on a phone; a row with a reason, or a dense one, keeps its height.
  const wraps = !reason && !dense
  const due = task.due ? formatShortDate(task.due) : null
  return (
    <CardRow
      lines={reason ? 2 : 1}
      aria-current={selected ? 'true' : undefined}
      className={cn('grid-cols-[1.75rem_minmax(0,1fr)_auto]', wraps && 'max-sm:min-h-12', dense && !reason && 'min-h-8 py-0', selected && 'bg-inset')}
    >
      <PriorityMark priority={task.priority} />
      <div className="flex min-w-0 flex-col">
        <div className="flex min-w-0 items-baseline gap-2">
          <Link
            to={href.note(task.path)}
            className={cn('linkbtn t-body', wraps ? 'max-sm:line-clamp-2 sm:truncate' : 'truncate')}
            onClick={(event) => {
              if (!onOpen || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
              event.preventDefault()
              onOpen(task)
            }}
          >
            {task.title}
          </Link>
          {!reason && project && <span className="t-small hidden truncate text-muted-ink sm:inline">{project}</span>}
          {!reason && due && (
            <span className={`num t-caption ml-auto flex-none ${overdue ? 'font-semibold text-status-blocked' : 'text-muted-ink'}`}>
              {overdue ? `Overdue, ${due}` : `Due ${due}`}
            </span>
          )}
        </div>
        {reason && (
          <span className="t-small truncate text-muted-ink">
            {reason}
            {project ? ` · ${project}` : ''}
          </span>
        )}
      </div>
      {status ?? <StatusChip status={task.status} />}
    </CardRow>
  )
}

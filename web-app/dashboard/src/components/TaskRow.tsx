import type { ReactNode } from 'react'
import { Link } from 'react-router'
import type { NoteSummary } from '@/api/types'
import { isOverdue } from '@/domain/tasks'
import { useToday } from '@/lib/clock'
import { formatShortDate } from '@/lib/dates'
import { noteHref } from '@/lib/routes'
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
 * `status` defaults to a read-only chip; pass a `StatusMenu` to make it editable.
 */
export function TaskRow({
  task,
  project,
  reason,
  status,
}: {
  task: NoteSummary
  /** Display name of the task's project, already resolved. */
  project?: string
  reason?: ReactNode
  status?: ReactNode
}) {
  const today = useToday()
  const overdue = isOverdue(task, today)
  const due = task.due ? formatShortDate(task.due) : null
  return (
    <CardRow lines={reason ? 2 : 1} className="grid-cols-[1.75rem_minmax(0,1fr)_auto]">
      <PriorityMark priority={task.priority} />
      <div className="flex min-w-0 flex-col">
        <div className="flex min-w-0 items-baseline gap-2">
          <Link to={noteHref(task.path)} className="linkbtn t-body truncate">
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

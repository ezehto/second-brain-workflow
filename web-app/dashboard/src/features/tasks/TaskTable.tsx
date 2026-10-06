import { Link } from 'react-router'
import type { NoteSummary } from '@/api/types'
import { StatusMenu } from '@/components/StatusMenu'
import { TaskRow } from '@/components/TaskRow'
import { isOverdue } from '@/domain/tasks'
import type { ProjectLookup } from '@/domain/projects'
import { useToday } from '@/lib/clock'
import { formatShortDate } from '@/lib/dates'
import { projectHref } from '@/lib/routes'
import type { GroupBy } from './filters'
import type { TaskGroup } from './grouping'

function dueText(task: NoteSummary, today: string): string {
  if (!task.due) return 'No due date'
  return isOverdue(task, today) ? `Overdue, ${formatShortDate(task.due)}` : `Due ${formatShortDate(task.due)}`
}

/**
 * Tasks as grouped dense rows (32px): priority, title, project and due date,
 * and the status control in place. On a phone each row has two lines (the due
 * date under the title) and the rows are 48px, so nothing is wider than the
 * screen. `onOpen` is given only when a split pane can show the note.
 */
export function TaskTable({
  groups,
  by,
  projects,
  phone,
  selectedPath,
  onOpen,
}: {
  groups: TaskGroup[]
  by: GroupBy
  projects: ProjectLookup
  phone: boolean
  selectedPath?: string
  onOpen?: (task: NoteSummary) => void
}) {
  const today = useToday()
  return (
    <div>
      {groups.map((group) => (
        <section key={group.key} aria-labelledby={`group-${group.key}`}>
          <div className="flex min-h-8 items-center justify-between gap-3 border-t border-line bg-inset px-3">
            <h3 id={`group-${group.key}`} className="t-small font-semibold">
              {group.projectSlug ? <Link to={projectHref(group.projectSlug)}>{group.label}</Link> : group.label}
            </h3>
            <span className="num t-caption text-muted-ink">
              <span className="sr-only">Tasks: </span>
              {group.tasks.length}
            </span>
          </div>
          <ul className="m-0 list-none p-0">
            {group.tasks.map((task) => (
              <li key={task.path}>
                <TaskRow
                  dense
                  task={task}
                  project={by !== 'project' && task.project ? projects.title(task.project) : undefined}
                  reason={phone ? dueText(task, today) : undefined}
                  selected={task.path === selectedPath}
                  onOpen={onOpen}
                  status={<StatusMenu note={task} />}
                />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

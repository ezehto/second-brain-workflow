import type { NoteSummary } from '@/api/types'
import { Card, CardHead } from '@/components/Card'
import { EmptyState } from '@/components/EmptyState'
import { StatusMenu } from '@/components/StatusMenu'
import { TaskRow } from '@/components/TaskRow'
import { isOverdue } from '@/domain/tasks'
import { useToday } from '@/lib/clock'
import { formatShortDate } from '@/lib/dates'
import { groupByStatus } from './domain'

function dueText(task: NoteSummary, today: string): string {
  if (!task.due) return 'No due date'
  return isOverdue(task, today) ? `Overdue, ${formatShortDate(task.due)}` : `Due ${formatShortDate(task.due)}`
}

/** The project's tasks as dense rows grouped by status. `onOpen` is given only when a split pane can show the note. */
export function TasksTab({
  tasks,
  phone,
  selectedPath,
  onOpen,
}: {
  tasks: NoteSummary[]
  phone: boolean
  selectedPath?: string
  onOpen?: (task: NoteSummary) => void
}) {
  const today = useToday()
  const groups = groupByStatus(tasks)
  return (
    <Card>
      <CardHead title="Tasks" count={tasks.length} />
      {groups.length === 0 ? (
        <EmptyState>No tasks in this project yet. Use New in the header to add one.</EmptyState>
      ) : (
        groups.map((group) => (
          <section key={group.status} aria-labelledby={`status-${group.status}`}>
            <div className="flex min-h-8 items-center justify-between gap-3 border-t border-line bg-inset px-3">
              <h3 id={`status-${group.status}`} className="t-small font-semibold">
                {group.status}
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
                    reason={phone ? dueText(task, today) : undefined}
                    selected={task.path === selectedPath}
                    onOpen={onOpen}
                    status={<StatusMenu note={task} />}
                  />
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </Card>
  )
}

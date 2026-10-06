import type { HealthLabel } from '@/domain/health'
import { todaysFocus } from '@/domain/focus'
import { isOpen, isOverdue, priorityRank } from '@/domain/tasks'
import { TASK_STATUSES, type NoteSummary } from '@/api/types'
import type { IsoDate } from '@/lib/clock'

/** Order of the Projects list: what needs attention first. */
export const HEALTH_SEVERITY: Record<HealthLabel, number> = {
  Blocked: 0,
  'At risk': 1,
  'Unknown, insufficient data': 2,
  'On track': 3,
  Completed: 4,
}

const byPriorityDueTitle = (a: NoteSummary, b: NoteSummary) =>
  priorityRank(a.priority) - priorityRank(b.priority) ||
  (a.due ?? '9999').localeCompare(b.due ?? '9999') ||
  a.title.localeCompare(b.title)

/**
 * Open tasks in Focus order: the Focus rule's groups first (overdue, blocked,
 * due today, in review), then every other open task by priority, due date and
 * title.
 */
export function focusOrdered(tasks: NoteSummary[], today: IsoDate): NoteSummary[] {
  const open = tasks.filter(isOpen)
  const focus = todaysFocus(open, today, open.length).map((item) => item.task)
  const chosen = new Set(focus.map((t) => t.path))
  return [...focus, ...open.filter((t) => !chosen.has(t.path)).sort(byPriorityDueTitle)]
}

/** The task to do next in a project: the first Focus-ordered open task that is not a bare inbox item. */
export function nextTask(tasks: NoteSummary[], today: IsoDate): NoteSummary | null {
  return focusOrdered(tasks, today).find((t) => t.status !== 'inbox') ?? null
}

export interface ProjectCounts {
  open: number
  blocked: number
  overdue: number
}

export function projectCounts(tasks: NoteSummary[], today: IsoDate): ProjectCounts {
  const open = tasks.filter(isOpen)
  return {
    open: open.length,
    blocked: open.filter((t) => t.status === 'blocked').length,
    overdue: open.filter((t) => isOverdue(t, today)).length,
  }
}

/** The latest modified time among the project note and its tasks (same offset, so strings compare). */
export function lastActivity(projectModified: string, tasks: NoteSummary[]): string {
  return tasks.reduce((latest, t) => (t.modified > latest ? t.modified : latest), projectModified)
}

export interface StatusGroup {
  status: string
  tasks: NoteSummary[]
}

/** Tasks by status in the fixed status order, non-empty groups only; statuses outside the vocabulary go last. */
export function groupByStatus(tasks: NoteSummary[]): StatusGroup[] {
  const known = TASK_STATUSES as readonly string[]
  const other = tasks.filter((t) => !known.includes(t.status ?? ''))
  const groups = TASK_STATUSES.map((status) => ({ status: status as string, tasks: tasks.filter((t) => t.status === status).sort(byPriorityDueTitle) }))
  if (other.length) groups.push({ status: 'other status', tasks: other.sort(byPriorityDueTitle) })
  return groups.filter((g) => g.tasks.length > 0)
}

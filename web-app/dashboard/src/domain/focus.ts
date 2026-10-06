import type { IsoDate } from '@/lib/clock'
import { daysBetween, NOT_AVAILABLE } from '@/lib/dates'
import { plural } from '@/lib/plural'
import type { NoteSummary } from '@/api/types'
import { byPriorityDueTitle, isOpen, isOverdue, priorityRank } from './tasks'

export type FocusGroup = 'overdue' | 'blocked' | 'due-today' | 'review'
const GROUP_ORDER: FocusGroup[] = ['overdue', 'blocked', 'due-today', 'review']

export interface FocusItem {
  rank: number
  task: NoteSummary
  group: FocusGroup
  /** One line saying why the task is here. */
  reason: string
}

export const FOCUS_RULE =
  'Chosen by a fixed rule, not by an AI: overdue first, then blocked, then due today, then in review. ' +
  'Within a group, high priority first, then the earliest due date. Five at most. Tasks in the inbox are not in focus.'

function groupOf(task: NoteSummary, today: IsoDate): FocusGroup | null {
  if (!isOpen(task) || task.status === 'inbox') return null
  if (isOverdue(task, today)) return 'overdue'
  if (task.status === 'blocked') return 'blocked'
  if (task.due === today) return 'due-today'
  if (task.status === 'review') return 'review'
  return null
}

function reasonOf(task: NoteSummary, group: FocusGroup, today: IsoDate): string {
  const by = task.blocked_by ?? NOT_AVAILABLE
  switch (group) {
    case 'overdue': {
      const late = plural(daysBetween(task.due as string, today), 'day')
      return `Overdue ${late}${task.status === 'blocked' ? `, blocked: ${by}` : ''}`
    }
    case 'blocked':
      return `Blocked: ${by}`
    case 'due-today':
      return `Due today${task.status === 'review' ? ', in review' : task.status === 'in-progress' ? ', in progress' : ''}`
    case 'review':
      return 'In review'
  }
}

/** Today's focus: the fixed ordering rule from the design, at most `limit` tasks. */
export function todaysFocus(tasks: NoteSummary[], today: IsoDate, limit = 5): FocusItem[] {
  return tasks
    .flatMap((task) => {
      const group = groupOf(task, today)
      return group ? [{ task, group }] : []
    })
    .sort(
      (a, b) =>
        GROUP_ORDER.indexOf(a.group) - GROUP_ORDER.indexOf(b.group) ||
        priorityRank(a.task.priority) - priorityRank(b.task.priority) ||
        (a.task.due ?? '9999').localeCompare(b.task.due ?? '9999') ||
        a.task.path.localeCompare(b.task.path),
    )
    .slice(0, limit)
    .map(({ task, group }, i) => ({ rank: i + 1, task, group, reason: reasonOf(task, group, today) }))
}

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

/**
 * The one "next item" rule of a project, on the Dashboard and on both project
 * pages: the first Focus-ordered open task that is not a bare inbox item.
 */
export function nextTask(tasks: NoteSummary[], today: IsoDate): NoteSummary | null {
  return focusOrdered(tasks, today).find((t) => t.status !== 'inbox') ?? null
}

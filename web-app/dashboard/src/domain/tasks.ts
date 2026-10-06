import type { IsoDate } from '@/lib/clock'
import type { NoteSummary, Priority, TaskStatus } from '@/api/types'
import { TASK_STATUSES } from '@/api/types'
import { isTaskStatus } from './status'

/** Not finished and not dropped. */
export function isOpen(task: NoteSummary): boolean {
  return task.status !== 'done' && task.status !== 'cancelled'
}

/** Open, with a due date before `today`. Dates compare as `YYYY-MM-DD` strings. */
export function isOverdue(task: NoteSummary, today: IsoDate): boolean {
  return !!task.due && task.due < today && isOpen(task)
}

/** The standup carry-forward set the "For today" tile counts: in progress, in review, and planned tasks due today or earlier. */
export function isForToday(task: NoteSummary, today: IsoDate): boolean {
  return task.status === 'in-progress' || task.status === 'review' || (task.status === 'planned' && !!task.due && task.due <= today)
}

/** Order by priority, then earliest due date, then title. */
export const byPriorityDueTitle = (a: NoteSummary, b: NoteSummary) =>
  priorityRank(a.priority) - priorityRank(b.priority) ||
  (a.due ?? '9999').localeCompare(b.due ?? '9999') ||
  a.title.localeCompare(b.title)

export const PRIORITY_RANK: Record<Priority, number> = { high: 0, medium: 1, low: 2 }

/** Rank for sorting; no priority, or one outside high/medium/low, sorts after `low`. */
export function priorityRank(priority: Priority | null): number {
  const rank = priority ? (PRIORITY_RANK as Record<string, number | undefined>)[priority] : undefined
  return rank ?? 3
}

export interface StatusCount {
  status: TaskStatus
  count: number
}

/** Counts per task status in the fixed status order; zero counts are left out. */
export function countByStatus(tasks: NoteSummary[]): StatusCount[] {
  return TASK_STATUSES.map((status) => ({
    status,
    count: tasks.filter((t) => t.status === status).length,
  })).filter((s) => s.count > 0)
}

/** Tasks whose status is outside the task vocabulary; they are in no donut segment. */
export function countUnknownStatus(tasks: NoteSummary[]): number {
  return tasks.filter((t) => !isTaskStatus(t.status)).length
}

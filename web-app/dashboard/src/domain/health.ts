import type { IsoDate } from '@/lib/clock'
import { NOT_AVAILABLE } from '@/lib/dates'
import { plural } from '@/lib/plural'
import type { NoteSummary, ProjectSummary } from '@/api/types'
import type { StatusTone } from './status'
import { isOpen, isOverdue } from './tasks'

export type HealthLabel = 'Completed' | 'Blocked' | 'At risk' | 'On track' | 'Unknown, insufficient data'

export interface ProjectHealth {
  label: HealthLabel
  tone: StatusTone
  reason: string
}

export const HEALTH_RULE =
  'Health is a rule, not a score. Completed: the project status is done. Blocked: at least one blocked task. ' +
  'At risk: at least one overdue open task. On track: open tasks, none blocked or overdue. ' +
  'Unknown: no tasks, or every task is done or cancelled.'

/** Health of one project from its own tasks. Rule order: done, blocked, overdue, open, unknown. */
export function projectHealth(project: Pick<ProjectSummary, 'status'>, tasks: NoteSummary[], today: IsoDate): ProjectHealth {
  const open = tasks.filter(isOpen)
  const blocked = open.filter((t) => t.status === 'blocked').length
  const overdue = open.filter((t) => isOverdue(t, today)).length
  if (project.status === 'done') return { label: 'Completed', tone: 'done', reason: 'Status is done' }
  if (blocked) return { label: 'Blocked', tone: 'blocked', reason: plural(blocked, 'blocked task') }
  if (overdue) return { label: 'At risk', tone: 'risk', reason: plural(overdue, 'overdue open task') }
  if (open.length) return { label: 'On track', tone: 'done', reason: `${open.length} open, none blocked or overdue` }
  return {
    label: 'Unknown, insufficient data',
    tone: 'neutral',
    reason: tasks.length ? 'No open tasks' : 'No tasks',
  }
}

export interface ProjectProgress {
  done: number
  /** Tasks that count: everything except cancelled. */
  total: number
  /** 0 to 100, or null when there is nothing to count. */
  percent: number | null
  /** "1 of 4 done", or `N/A` when there is nothing to count. */
  text: string
}

/** Progress as counts: cancelled tasks are not part of the total. */
export function projectProgress(tasks: NoteSummary[]): ProjectProgress {
  const counted = tasks.filter((t) => t.status !== 'cancelled')
  const done = counted.filter((t) => t.status === 'done').length
  if (!counted.length) return { done, total: 0, percent: null, text: NOT_AVAILABLE }
  return { done, total: counted.length, percent: Math.round((done / counted.length) * 100), text: `${done} of ${counted.length} done` }
}

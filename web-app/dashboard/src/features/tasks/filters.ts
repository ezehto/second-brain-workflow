import type { NoteSummary } from '@/api/types'
import { isOpen, isOverdue } from '@/domain/tasks'
import type { IsoDate } from '@/lib/clock'
import type { TaskFilters } from '@/lib/routes'

export const GROUPS = ['project', 'status', 'due'] as const
export type GroupBy = (typeof GROUPS)[number]
export const DEFAULT_GROUP: GroupBy = 'project'

/** What the Tasks URL holds: the contract filters of `lib/routes.ts`, plus how to group and which note is open. */
export interface TaskView {
  filters: TaskFilters
  group: GroupBy
  /** Vault path of the note open in the split pane. */
  note?: string
}

/** `status=all` is the explicit "no status filter"; it is never written to the URL. */
export function parseTaskParams(params: URLSearchParams): TaskView {
  const status = params.get('status')
  const group = params.get('group')
  return {
    filters: {
      status: status && status !== 'all' ? status : undefined,
      priority: params.get('priority') || undefined,
      project: params.get('project') || undefined,
      today: params.get('today') === 'true' || undefined,
      overdue: params.get('overdue') === 'true' || undefined,
    },
    group: (GROUPS as readonly string[]).includes(group ?? '') ? (group as GroupBy) : DEFAULT_GROUP,
    note: params.get('note') || undefined,
  }
}

/** The inverse of `parseTaskParams`. Filter keys match `tasksHref`; `group` is written only when not the default. */
export function buildTaskParams({ filters, group, note }: TaskView): URLSearchParams {
  const q = new URLSearchParams()
  if (filters.status) q.set('status', filters.status)
  if (filters.priority) q.set('priority', filters.priority)
  if (filters.project) q.set('project', filters.project)
  if (filters.today) q.set('today', 'true')
  if (filters.overdue) q.set('overdue', 'true')
  if (group !== DEFAULT_GROUP) q.set('group', group)
  if (note) q.set('note', note)
  return q
}

export const hasFilters = (f: TaskFilters) => Object.values(f).some(Boolean)

/** The standup carry-forward set the "For today" tile counts: in progress, in review, and planned tasks due today or earlier. */
export function isForToday(task: NoteSummary, today: IsoDate): boolean {
  return task.status === 'in-progress' || task.status === 'review' || (task.status === 'planned' && !!task.due && task.due <= today)
}

/**
 * The tasks matching the filters. `ignoreStatus` leaves the status filter out,
 * which is how the distribution bar counts every status under the other filters.
 */
export function applyTaskFilters(tasks: NoteSummary[], filters: TaskFilters, today: IsoDate, { ignoreStatus = false } = {}): NoteSummary[] {
  return tasks.filter((t) => {
    if (!ignoreStatus && filters.status && (filters.status === 'open' ? !isOpen(t) : t.status !== filters.status)) return false
    if (filters.priority && t.priority !== filters.priority) return false
    if (filters.project && t.project !== filters.project) return false
    if (filters.overdue && !isOverdue(t, today)) return false
    if (filters.today && !isForToday(t, today)) return false
    return true
  })
}

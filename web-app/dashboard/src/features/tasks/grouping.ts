import type { NoteSummary } from '@/api/types'
import { TASK_STATUSES } from '@/api/types'
import { isOpen, isOverdue, priorityRank } from '@/domain/tasks'
import type { ProjectLookup } from '@/domain/projects'
import { daysBetween } from '@/lib/dates'
import type { IsoDate } from '@/lib/clock'
import type { GroupBy } from './filters'

export interface TaskGroup {
  key: string
  label: string
  /** The project slug when grouping by project and the slug names a project note. */
  projectSlug?: string
  tasks: NoteSummary[]
}

/** Open tasks first, then priority (high first), then the earliest due date; no due date last. */
export function compareTasks(a: NoteSummary, b: NoteSummary): number {
  return (
    Number(!isOpen(a)) - Number(!isOpen(b)) ||
    priorityRank(a.priority) - priorityRank(b.priority) ||
    (a.due ?? '9999').localeCompare(b.due ?? '9999') ||
    a.title.localeCompare(b.title)
  )
}

const DUE_BUCKETS = ['Overdue', 'Due today', 'Next 7 days', 'Later', 'No due date', 'Closed'] as const

function dueBucket(task: NoteSummary, today: IsoDate): (typeof DUE_BUCKETS)[number] {
  if (!isOpen(task)) return 'Closed'
  if (isOverdue(task, today)) return 'Overdue'
  if (!task.due) return 'No due date'
  const days = daysBetween(today, task.due)
  if (days === 0) return 'Due today'
  return days <= 7 ? 'Next 7 days' : 'Later'
}

const NO_PROJECT = 'No project'
const OTHER_STATUS = 'Other status'

/** Sorts the tasks and splits them into the non-empty groups, in a fixed group order. */
export function groupTasks(tasks: NoteSummary[], by: GroupBy, today: IsoDate, projects: ProjectLookup): TaskGroup[] {
  const sorted = [...tasks].sort(compareTasks)
  const buckets = new Map<string, TaskGroup>()
  const add = (key: string, label: string, task: NoteSummary, projectSlug?: string) => {
    const group = buckets.get(key) ?? { key, label, projectSlug, tasks: [] }
    group.tasks.push(task)
    buckets.set(key, group)
  }

  for (const task of sorted) {
    if (by === 'project') {
      const slug = task.project
      add(slug ?? '', slug ? projects.title(slug) : NO_PROJECT, task, slug && projects.known(slug) ? slug : undefined)
    } else if (by === 'status') {
      const known = (TASK_STATUSES as readonly string[]).includes(task.status ?? '')
      add(known ? (task.status as string) : OTHER_STATUS, known ? (task.status as string) : OTHER_STATUS, task)
    } else {
      const bucket = dueBucket(task, today)
      add(bucket, bucket, task)
    }
  }

  const groups = [...buckets.values()]
  if (by === 'project') {
    return groups.sort((a, b) => Number(a.key === '') - Number(b.key === '') || a.label.localeCompare(b.label))
  }
  const order: readonly string[] = by === 'status' ? [...TASK_STATUSES, OTHER_STATUS] : DUE_BUCKETS
  return groups.sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key))
}

import type { IsoDate } from '@/lib/clock'
import { tasksHref } from '@/lib/routes'
import { formatShortDate, NOT_AVAILABLE } from '@/lib/dates'
import type { NoteSummary } from '@/api/types'
import type { StatusTone } from './status'
import { isOpen, isOverdue } from './tasks'

export interface AttentionItem {
  task: NoteSummary
  note: string
}

export interface AttentionRow {
  key: 'blocked' | 'overdue' | 'high-priority' | 'in-review' | 'incidents'
  label: string
  /** null for a row the data cannot supply (incidents): shown as `N/A`. */
  count: number | null
  tone: StatusTone
  items: AttentionItem[]
  emptyText: string
  /** The task-list query this row links to, or null when it has no list yet. */
  to: string | null
}

const byDue = (a: NoteSummary, b: NoteSummary) =>
  (a.due ?? '9999').localeCompare(b.due ?? '9999') || a.title.localeCompare(b.title)

/** The "Needs attention" rows: blocked, overdue, high priority, in review, incidents. */
export function attentionRows(
  tasks: NoteSummary[],
  today: IsoDate,
  projectTitle: (slug: string | null) => string = (slug) => slug ?? NOT_AVAILABLE,
): AttentionRow[] {
  const blocked = tasks.filter((t) => t.status === 'blocked').sort(byDue)
  const overdue = tasks.filter((t) => isOverdue(t, today)).sort(byDue)
  const high = tasks.filter((t) => isOpen(t) && t.priority === 'high').sort(byDue)
  const review = tasks.filter((t) => t.status === 'review').sort(byDue)
  const row = (
    key: AttentionRow['key'],
    label: string,
    list: NoteSummary[],
    tone: StatusTone,
    note: (t: NoteSummary) => string,
    to: string,
    emptyText: string,
  ): AttentionRow => ({
    key,
    label,
    count: list.length,
    tone: list.length ? tone : 'neutral',
    items: list.map((task) => ({ task, note: note(task) })),
    emptyText,
    to,
  })
  return [
    row('blocked', 'Blocked', blocked, 'blocked', (t) => `blocked: ${t.blocked_by ?? NOT_AVAILABLE}`, tasksHref({ status: 'blocked' }), 'Nothing is blocked.'),
    row('overdue', 'Overdue', overdue, 'blocked', (t) => `due ${formatShortDate(t.due)}`, tasksHref({ status: 'open', overdue: true }), 'Nothing is overdue.'),
    row('high-priority', 'High priority', high, 'neutral', (t) => t.status ?? NOT_AVAILABLE, tasksHref({ status: 'open', priority: 'high' }), 'No open high-priority tasks.'),
    row('in-review', 'In review', review, 'review', (t) => projectTitle(t.project), tasksHref({ status: 'review' }), 'Nothing waiting for review.'),
    {
      key: 'incidents',
      label: 'Critical incidents',
      count: null,
      tone: 'neutral',
      items: [],
      emptyText: 'Incidents are not tracked yet. Phase 2.',
      to: null,
    },
  ]
}

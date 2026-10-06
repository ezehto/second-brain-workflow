import type { IsoDate } from '@/lib/clock'
import { daysBetween, wallDate } from '@/lib/dates'
import type { NoteSummary } from '@/api/types'

/** Tasks narrowed to a project (the context filter); null keeps everything. */
export function inProject<T extends { project: string | null }>(notes: T[], project: string | null): T[] {
  return project ? notes.filter((n) => n.project === project) : notes
}

/** Whole days since a note last changed, from its wall-clock `modified` date. Never negative. */
export function daysSinceModified(note: Pick<NoteSummary, 'modified'>, today: IsoDate): number {
  return Math.max(0, daysBetween(wallDate(note.modified), today))
}

/** Whole days since a note was created; null when it has no readable created date. */
export function daysSinceCreated(note: Pick<NoteSummary, 'created'>, today: IsoDate): number | null {
  return note.created ? Math.max(0, daysBetween(note.created.slice(0, 10), today)) : null
}

/** Blocked tasks, earliest due first. */
export function blockedTasks(tasks: NoteSummary[]): NoteSummary[] {
  return tasks
    .filter((t) => t.status === 'blocked')
    .sort((a, b) => (a.due ?? '9999').localeCompare(b.due ?? '9999') || a.title.localeCompare(b.title))
}

/** Proposed decisions, oldest first, so the longest-waiting is on top. */
export function proposedDecisions(decisions: NoteSummary[]): NoteSummary[] {
  return decisions
    .filter((d) => d.type === 'decision' && d.status === 'proposed')
    .sort((a, b) => (a.created ?? '').localeCompare(b.created ?? '') || a.title.localeCompare(b.title))
}

/** The 7 calendar days ending today, oldest first (`days` of them). */
export function lastDays(today: IsoDate, days = 7): IsoDate[] {
  return Array.from({ length: days }, (_, i) => {
    const d = new Date(`${today}T00:00:00Z`)
    d.setUTCDate(d.getUTCDate() - (days - 1 - i))
    return d.toISOString().slice(0, 10)
  })
}

/**
 * Tasks done in the last 7 days. Only the note's modified time is stored, so
 * the completion day is approximate: the day the note last changed.
 */
export function doneRecently(tasks: NoteSummary[], today: IsoDate): NoteSummary[] {
  const window = new Set(lastDays(today))
  return tasks
    .filter((t) => t.status === 'done' && window.has(wallDate(t.modified)))
    .sort((a, b) => b.modified.localeCompare(a.modified) || a.path.localeCompare(b.path))
}

export interface DayCount {
  date: IsoDate
  count: number
}

/** Done tasks per day over the last 7 days, oldest first, zero days included. */
export function doneByDay(done: NoteSummary[], today: IsoDate): DayCount[] {
  return lastDays(today).map((date) => ({ date, count: done.filter((t) => wallDate(t.modified) === date).length }))
}

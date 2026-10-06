import { daysBetween } from '@/lib/dates'
import type { PreviewTimelineEvent, TimelineSource } from '@/preview'

export const RANGES = [
  { value: '1', label: 'Today', days: 0 },
  { value: '7', label: '7 days', days: 7 },
  { value: '30', label: '30 days', days: 30 },
] as const

export const SOURCE_ORDER: TimelineSource[] = ['vault', 'jira', 'gitlab', 'calendar']

/** Status hues only (design rule): the four sources take four different status hues, each also named in the legend. */
export const SOURCE_COLOR: Record<TimelineSource, string> = {
  vault: 'var(--color-status-review)',
  jira: 'var(--color-status-progress)',
  gitlab: 'var(--color-status-risk)',
  calendar: 'var(--color-status-done)',
}

export const STATUS_WORD: Record<PreviewTimelineEvent['status'], string> = {
  open: 'Open',
  review: 'In review',
  blocked: 'Blocked',
  done: 'Done',
  na: 'N/A',
}
export const STATUS_TONE = { open: 'progress', review: 'review', blocked: 'blocked', done: 'done', na: 'neutral' } as const

export interface TimelineFilters {
  range: string
  project: string
  source: string
  type: string
}

export const DEFAULT_FILTERS: TimelineFilters = { range: '7', project: 'all', source: 'all', type: 'all' }

export function rangeDays(range: string): number {
  return RANGES.find((r) => r.value === range)?.days ?? 7
}

export const inRange = (events: PreviewTimelineEvent[], range: string, asOf: string) =>
  events.filter((e) => daysBetween(e.date, asOf) <= rangeDays(range))

export function applyFilters(events: PreviewTimelineEvent[], f: TimelineFilters, asOf: string): PreviewTimelineEvent[] {
  return inRange(events, f.range, asOf).filter(
    (e) =>
      (f.project === 'all' || e.projects.includes(f.project)) &&
      (f.source === 'all' || e.source === f.source) &&
      (f.type === 'all' || e.type === f.type),
  )
}

const shiftDay = (date: string, by: number) => new Date(Date.parse(`${date}T00:00:00Z`) + by * 86_400_000).toISOString().slice(0, 10)

/** Every calendar day of the range, oldest first, with the events of each source on that day. */
export function dailyCounts(events: PreviewTimelineEvent[], range: string, asOf: string) {
  const days = rangeDays(range)
  return Array.from({ length: days + 1 }, (_, i) => {
    const date = shiftDay(asOf, i - days)
    const on = events.filter((e) => e.date === date)
    const bySource = Object.fromEntries(SOURCE_ORDER.map((s) => [s, on.filter((e) => e.source === s).length])) as Record<TimelineSource, number>
    return { date, total: on.length, bySource }
  })
}

export const CHART = { width: 600, height: 120 }

/** SVG path data for a stacked area per source, bottom layer first. Points sit at day centres so HTML labels line up. */
export function stackedPaths(days: ReturnType<typeof dailyCounts>): { source: TimelineSource; d: string }[] {
  const { width: W, height: H } = CHART
  const n = days.length
  const max = Math.max(1, ...days.map((d) => d.total))
  const x = (i: number) => (((i + 0.5) / n) * W).toFixed(1)
  const y = (v: number) => (H - 4 - (v / max) * (H - 12)).toFixed(1)
  const lower = days.map(() => 0)
  return SOURCE_ORDER.map((source) => {
    const upper = days.map((d, i) => lower[i] + d.bySource[source])
    const top = upper.map((v, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(v)}`).join(' ')
    const bottom = lower.map((_, i) => `L ${x(n - 1 - i)} ${y(lower[n - 1 - i])}`).join(' ')
    upper.forEach((v, i) => (lower[i] = v))
    return { source, d: `${top} ${bottom} Z` }
  })
}

export const slug = (e: PreviewTimelineEvent) => e.title.replace(/[:/\\]/g, '').slice(0, 70)

export interface EventAction {
  label: string
  verb: string
  file: string
}

/** Context-aware actions: what could be written for this kind of event, and the file it would touch. */
export function actionsFor(e: PreviewTimelineEvent): EventAction[] {
  const s = slug(e)
  const key = e.ref ?? s
  const externalNote = e.source === 'jira' ? `02-Work/Tickets/${key}.md` : `07-External-Context/${key}.md`
  const a = {
    task: { label: 'Create task', verb: 'create', file: `02-Work/Tasks/${s}.md` },
    note: { label: 'Create note', verb: 'create', file: externalNote },
    decision: { label: 'Create decision', verb: 'create', file: `05-Knowledge/Decisions/${s}.md` },
    lesson: { label: 'Create lesson', verb: 'create', file: `05-Knowledge/Lessons/${s}.md` },
    follow: { label: 'Create follow-up', verb: 'create', file: `02-Work/Follow-ups/Follow up ${s}.md` },
    link: { label: 'Link to project', verb: 'set project in', file: externalNote },
    start: { label: 'Start implementation', verb: 'create', file: `02-Work/Tasks/Implement ${key}.md (status in-progress)` },
    meeting: { label: 'Create meeting note', verb: 'create', file: `02-Work/Meetings/${e.date} ${s}.md` },
  }
  const byType: Record<string, EventAction[]> = {
    ticket: [a.task, a.note, a.decision, a.follow, a.link, a.start],
    meeting: [a.meeting, a.follow, a.decision, a.task],
    mr: [a.task, a.note, a.follow, a.link],
    commit: [a.note, a.lesson, a.follow],
    review: [a.follow, a.lesson, a.note],
    deploy: [a.follow, a.task, a.note],
    incident: [a.task, a.lesson, a.decision, a.follow, a.note],
    'task-created': [a.follow, a.decision, a.note],
    'task-completed': [a.lesson, a.follow],
    standup: [a.follow],
    decision: [a.task, a.follow],
    lesson: [a.task, a.decision],
    document: [a.follow, a.task],
    learning: [a.lesson, a.task],
  }
  return byType[e.type] ?? [a.follow]
}

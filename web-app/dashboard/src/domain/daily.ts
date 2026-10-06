import type { IsoDate } from '@/lib/clock'
import { daysBetween, formatDayTitle, formatShortDate } from '@/lib/dates'
import { STANDUP_SECTIONS, type StandupPreview, type StandupSection } from '@/api/types'
import { sectionLines } from './standup'

/** One list line of a daily note section, parsed. */
export interface DailyLine {
  /** The line as written, e.g. `- [ ] [[Fix N+1 query]]`. */
  raw: string
  /** `null` for a plain bullet, otherwise the checkbox state. */
  checked: boolean | null
  /** The line without its bullet and checkbox. */
  text: string
  /** Wikilink targets, in order (alias and heading parts removed). */
  links: string[]
  /** Identity across days: the first link, else the text, lower-cased and whitespace-collapsed. */
  key: string
}

export type DailySections = Record<StandupSection, DailyLine[]>

export interface DailyDay {
  date: IsoDate
  path: string
  sections: DailySections
}

const WIKILINK = /\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]/g

export function wikilinkTargets(text: string): string[] {
  return [...text.matchAll(WIKILINK)].map((m) => m[1].trim())
}

export type TextSegment = { kind: 'text'; value: string } | { kind: 'link'; target: string; label: string }

/** Splits text into plain runs and wikilinks, so a renderer can link the latter. */
export function textSegments(text: string): TextSegment[] {
  const out: TextSegment[] = []
  let last = 0
  for (const m of text.matchAll(WIKILINK)) {
    const at = m.index ?? 0
    if (at > last) out.push({ kind: 'text', value: text.slice(last, at) })
    out.push({ kind: 'link', target: m[1].trim(), label: (m[2] ?? m[1]).trim() })
    last = at + m[0].length
  }
  if (last < text.length) out.push({ kind: 'text', value: text.slice(last) })
  return out
}

const normalise = (text: string) => text.replace(/\s+/g, ' ').trim().toLowerCase()

export function parseLine(raw: string): DailyLine {
  const m = /^[-*+] (?:\[([ xX])\] )?(.*)$/.exec(raw.trim())
  const text = (m ? m[2] : raw).trim()
  const links = wikilinkTargets(text)
  return {
    raw,
    checked: m?.[1] === undefined ? null : m[1] !== ' ',
    text,
    links,
    key: links.length ? links[0].toLowerCase() : normalise(text),
  }
}

/** The six standup sections of a note body, each as parsed lines (a missing heading is empty). */
export function parseDaily(body: string): DailySections {
  return Object.fromEntries(STANDUP_SECTIONS.map((h) => [h, sectionLines(body, h).map(parseLine)])) as DailySections
}

/** The carry-forward preview in the same shape as a parsed note. */
export function previewSections(preview: StandupPreview): DailySections {
  return Object.fromEntries(STANDUP_SECTIONS.map((h) => [h, preview[h].map(parseLine)])) as DailySections
}

/** `01-Daily/2026/2026-10-06.md` to `2026-10-06`. */
export function dateOfDailyPath(path: string): IsoDate {
  return path.slice(path.lastIndexOf('/') + 1).replace(/\.md$/, '')
}

/** The latest day strictly before `date`, from days in any order. */
export function previousDay<T extends { date: IsoDate }>(days: T[], date: IsoDate): T | null {
  return days.filter((d) => d.date < date).sort((a, b) => b.date.localeCompare(a.date))[0] ?? null
}

/** A line that has been in a section on consecutive standups, up to the newest one. */
export interface Run {
  key: string
  label: string
  line: DailyLine
  /** The date of the oldest standup in the run. */
  since: IsoDate
  /** How many standups in a row list it, the newest included. */
  standups: number
}

/**
 * Unchecked lines of the newest day's `section`, each with how many standups
 * in a row (newest first) have listed it unchecked. Duplicates within a day
 * count once.
 */
export function openRuns(daysNewestFirst: DailyDay[], section: StandupSection): Run[] {
  const [newest, ...older] = daysNewestFirst
  if (!newest) return []
  const seen = new Set<string>()
  const runs: Run[] = []
  for (const line of newest.sections[section]) {
    if (line.checked === true || seen.has(line.key)) continue
    seen.add(line.key)
    let standups = 1
    let since = newest.date
    for (const day of older) {
      if (!day.sections[section].some((l) => l.key === line.key && l.checked !== true)) break
      standups += 1
      since = day.date
    }
    runs.push({ key: line.key, label: line.links[0] ?? line.text, line, since, standups })
  }
  return runs
}

export const CARRY_OVER_DAYS = 3

export function carryOverItems(daysNewestFirst: DailyDay[]): Run[] {
  return openRuns(daysNewestFirst, 'Today').filter((r) => r.standups >= CARRY_OVER_DAYS)
}

export interface RecurringBlocker {
  key: string
  label: string
  /** Dates (oldest first) of the standups that list it. */
  dates: IsoDate[]
  blockedBy: string | null
}

const BLOCKED_BY = /\(blocked by:\s*(.*)\)\s*$/i

/** Blockers listed on two or more standups, most days first. */
export function recurringBlockers(days: DailyDay[]): RecurringBlocker[] {
  const byKey = new Map<string, RecurringBlocker>()
  for (const day of [...days].sort((a, b) => a.date.localeCompare(b.date))) {
    const seenToday = new Set<string>()
    for (const line of day.sections.Blockers) {
      if (seenToday.has(line.key)) continue
      seenToday.add(line.key)
      const entry = byKey.get(line.key) ?? { key: line.key, label: line.links[0] ?? line.text.replace(BLOCKED_BY, '').trim(), dates: [], blockedBy: null }
      entry.dates.push(day.date)
      entry.blockedBy = BLOCKED_BY.exec(line.text)?.[1] ?? entry.blockedBy
      byKey.set(line.key, entry)
    }
  }
  return [...byKey.values()].filter((b) => b.dates.length >= 2).sort((a, b) => b.dates.length - a.dates.length || a.label.localeCompare(b.label))
}

export const WORK_WINDOW = 5

export interface WorkByProject {
  /** Project slug, or null for work that resolves to no project. */
  slug: string | null
  count: number
}

/**
 * Lines under Done over the newest `WORK_WINDOW` standups, counted by project.
 * `projectOf` maps one line to its project slug (the page resolves the line's
 * links against tasks and projects).
 */
export function workByProject(daysNewestFirst: DailyDay[], projectOf: (line: DailyLine) => string | null): WorkByProject[] {
  const counts = new Map<string | null, number>()
  for (const day of daysNewestFirst.slice(0, WORK_WINDOW)) {
    for (const line of day.sections.Done) {
      const slug = projectOf(line)
      counts.set(slug, (counts.get(slug) ?? 0) + 1)
    }
  }
  return [...counts.entries()]
    .map(([slug, count]) => ({ slug, count }))
    .sort((a, b) => b.count - a.count || (a.slug === null ? 1 : b.slug === null ? -1 : a.slug.localeCompare(b.slug)))
}

export interface OpenFollowUp extends Run {
  /** Whole days since the oldest standup that listed it. */
  ageDays: number
}

export function openFollowUps(daysNewestFirst: DailyDay[], today: IsoDate): OpenFollowUp[] {
  return openRuns(daysNewestFirst, 'Follow-ups').map((r) => ({ ...r, ageDays: daysBetween(r.since, today) }))
}

/** What the four stat tiles count, from the lines on screen. */
export function standupCounts(sections: DailySections, todayRuns: Run[]) {
  const carried = new Set(todayRuns.filter((r) => r.standups >= 2).map((r) => r.key))
  return {
    planned: sections.Today.length,
    carried: sections.Today.filter((l) => l.checked !== true && carried.has(l.key)).length,
    blockers: sections.Blockers.length,
    followUps: sections['Follow-ups'].filter((l) => l.checked !== true).length,
  }
}

const plainLine = (line: DailyLine, done: boolean) => {
  const text = line.text.replace(WIKILINK, (_, target: string, alias?: string) => (alias ?? target).trim())
  return `- ${text}${done && line.checked ? ', done' : ''}`
}

/** The standup as text to paste into chat. */
export function standupAsText(input: { date: IsoDate; yesterday: DailyDay | null; sections: DailySections }): string {
  const out: string[] = [`Standup, ${formatDayTitle(input.date)}`]
  const block = (title: string, lines: string[]) => {
    out.push('', `${title}:`, ...(lines.length ? lines : ['- none']))
  }
  if (input.yesterday) {
    block(`Yesterday (${formatShortDate(input.yesterday.date)}), done`, input.yesterday.sections.Done.map((l) => plainLine(l, false)))
  }
  const s = input.sections
  block('Done today', s.Done.map((l) => plainLine(l, false)))
  block('Today', s.Today.map((l) => plainLine(l, true)))
  block('Blockers', s.Blockers.map((l) => plainLine(l, false)))
  block('Decisions and updates', s['Decisions / Updates'].map((l) => plainLine(l, false)))
  block('Follow-ups', s['Follow-ups'].map((l) => plainLine(l, true)))
  out.push('', `Related: ${s['Related Tasks / Projects'].map((l) => l.links[0] ?? l.text).join(', ') || 'none'}`)
  return out.join('\n')
}

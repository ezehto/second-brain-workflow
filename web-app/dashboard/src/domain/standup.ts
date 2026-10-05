import type { IsoDate } from '@/lib/clock'
import type { StandupSection, StandupToday } from '@/api/types'

/** Where today's daily note lives, from the vault's today. */
export function dailyPath(today: IsoDate): string {
  return `01-Daily/${today.slice(0, 4)}/${today}.md`
}

/** The list lines (`- ...`) under a `## heading` of a note body. */
export function sectionLines(body: string, heading: StandupSection): string[] {
  const lines = body.split('\n')
  const start = lines.findIndex((l) => l.trim() === `## ${heading}`)
  if (start < 0) return []
  const out: string[] = []
  for (const line of lines.slice(start + 1)) {
    if (line.startsWith('## ')) break
    if (/^[-*+] /.test(line)) out.push(line)
  }
  return out
}

/** What the dashboard card needs from today's standup. Derived, not an API shape. */
export interface StandupSummary {
  path: string
  exists: boolean
  /** null while the note does not exist. */
  untouched: boolean | null
  /** Lines under Today and Blockers: carried forward (preview) or in the note. */
  today_count: number
  blocker_count: number
}

export function summarizeStandup(standup: StandupToday, today: IsoDate): StandupSummary {
  if (!standup.exists) {
    return { path: dailyPath(today), exists: false, untouched: null, today_count: standup.preview.Today.length, blocker_count: standup.preview.Blockers.length }
  }
  return {
    path: standup.note.path,
    exists: true,
    untouched: standup.untouched,
    today_count: sectionLines(standup.note.body, 'Today').length,
    blocker_count: sectionLines(standup.note.body, 'Blockers').length,
  }
}

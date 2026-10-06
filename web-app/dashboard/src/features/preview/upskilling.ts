import type { StatusTone } from '@/domain/status'
import type { PreviewLearningNote, PreviewSkill } from '@/preview'

export const CHAIN_LABELS = ['Production problem', 'Skill gap', 'Learning topic', 'Practice', 'Applied to project', 'Review', 'Lesson learned']

export const LEVEL_TONE: Record<PreviewSkill['level'], StatusTone> = {
  Aware: 'neutral',
  Practicing: 'progress',
  Applied: 'done',
  'Can teach': 'review',
}

export const KIND_FOLDER: Record<PreviewLearningNote['kind'], string> = { learning: 'Learning', practice: 'Practice', applied: 'Practice' }
export const notePath = (n: PreviewLearningNote) => `06-Upskilling/${KIND_FOLDER[n.kind]}/${n.title}.md`

const DAY = 86_400_000
const utc = (date: string) => Date.parse(`${date}T00:00:00Z`)

export const weekFile = (week: number) => `06-Upskilling/Roadmap/Week ${String(week).padStart(2, '0')}.md`

/** Monday of a roadmap week (1-based), as a UTC timestamp. */
export const weekStart = (start: string, week: number) => utc(start) + (week - 1) * 7 * DAY

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
export const monthDay = (ms: number) => `${MONTHS[new Date(ms).getUTCMonth()]} ${new Date(ms).getUTCDate()}`

export type WeekState = 'done' | 'partly' | 'current' | 'upcoming'
export const WEEK_WORD: Record<WeekState, string> = { done: 'Done', partly: 'Partly done', current: 'Now', upcoming: 'Next' }

export function weekState(week: number, current: number, states: Record<number, 'done' | 'partly'>): WeekState {
  return week === current ? 'current' : (states[week] ?? 'upcoming')
}

export interface WeekCount {
  week: number
  start: string
  learning: number
  practice: number
  applied: number
  total: number
}

/** Notes counted per roadmap week, week 1 to the current week. */
export function weeklyCounts(notes: PreviewLearningNote[], start: string, currentWeek: number): WeekCount[] {
  const counts: WeekCount[] = Array.from({ length: currentWeek }, (_, i) => ({
    week: i + 1,
    start: monthDay(weekStart(start, i + 1)),
    learning: 0,
    practice: 0,
    applied: 0,
    total: 0,
  }))
  for (const n of notes) {
    const w = Math.floor((utc(n.date) - utc(start)) / (7 * DAY))
    if (w < 0 || w >= currentWeek) continue
    counts[w][n.kind]++
    counts[w].total++
  }
  return counts
}

export const filledSteps = (skill: PreviewSkill) => skill.chain.filter(Boolean).length

export function groupByCategory(skills: PreviewSkill[]): [string, PreviewSkill[]][] {
  const map = new Map<string, PreviewSkill[]>()
  skills.forEach((s) => map.set(s.category, [...(map.get(s.category) ?? []), s]))
  return [...map]
}

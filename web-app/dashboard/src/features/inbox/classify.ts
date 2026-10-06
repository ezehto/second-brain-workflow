import type { NoteDetail, TriageAction } from '@/api/types'
import { formatShortDate, formatWhen } from '@/lib/dates'

/** The ten allowed `classification` values (plan section 2.13). */
export const CLASSIFICATIONS = [
  'task',
  'problem',
  'decision',
  'learning-topic',
  'note',
  'project',
  'ticket',
  'architecture-idea',
  'question',
  'thought',
] as const
export type Classification = (typeof CLASSIFICATIONS)[number]

type Conversion = Exclude<TriageAction, 'keep' | 'dismiss'>

const TARGET: Partial<Record<string, Conversion>> = {
  task: 'task',
  problem: 'task',
  decision: 'decision',
  'learning-topic': 'lesson',
  note: 'lesson',
  project: 'project',
}

const LABEL: Record<Conversion, string> = {
  task: 'Create task',
  decision: 'Create decision',
  lesson: 'Create lesson',
  project: 'Create project note',
}

/** The Phase 1 conversion a classification maps to, or null when it has no target yet. */
export const conversionOf = (classification: string): Conversion | null => TARGET[classification] ?? null

/** The one action button's label, which follows the chosen classification. */
export const actionLabel = (classification: string): string => {
  const conversion = conversionOf(classification)
  return conversion ? LABEL[conversion] : 'Keep in inbox'
}

export const isClassification = (value: unknown): value is Classification => CLASSIFICATIONS.includes(value as Classification)

/** The classification `/triage` wrote, or '' when there is none (or an unknown value). */
export const writtenClassification = (note: NoteDetail): string => {
  const value = note.frontmatter.classification
  return isClassification(value) ? value : ''
}

/** The capture text: the body's first line, else the file name without its date and time prefix. */
export function captureText(note: NoteDetail): string {
  const line = note.body
    .split('\n')
    .map((l) => l.trim())
    .find((l) => l !== '' && !l.startsWith('#'))
  return line ?? (note.title.replace(/^\d{4}-\d{2}-\d{2} \d{4,6} ?/, '').trim() || note.title)
}

/** When it was captured: the time for today, else the date and time. Capture names start `YYYY-MM-DD HHmm`. */
export function capturedWhen(note: NoteDetail, today: string): string {
  const match = /^(\d{4}-\d{2}-\d{2}) (\d{2})(\d{2})/.exec(note.title)
  if (!match) return formatWhen(note.modified, today)
  const time = `${match[2]}:${match[3]}`
  return match[1] === today ? time : `${formatShortDate(match[1])}, ${time}`
}

import { TASK_STATUSES, type TaskStatus, type VocabularyStatus } from '@/api/types'

/** Colour roles a status can have. Each maps to one token in index.css. */
export type StatusTone = 'neutral' | 'progress' | 'blocked' | 'risk' | 'done' | 'review' | 'cancelled'

// Typed against the vocabularies: a status added to one must be given a tone here.
const TONES: Record<VocabularyStatus, StatusTone> = {
  // task
  inbox: 'neutral',
  planned: 'neutral',
  'in-progress': 'progress',
  blocked: 'blocked',
  review: 'review',
  done: 'done',
  cancelled: 'cancelled',
  // project, decision, lesson, capture
  active: 'progress',
  paused: 'neutral',
  archived: 'cancelled',
  proposed: 'neutral',
  accepted: 'done',
  superseded: 'cancelled',
  rejected: 'cancelled',
  triaged: 'done',
  dismissed: 'cancelled',
}

/** The colour role of a status. A value outside the vocabularies is neutral. */
export function statusTone(status: string | null | undefined): StatusTone {
  return (status && (TONES as Record<string, StatusTone | undefined>)[status]) || 'neutral'
}

/** Tailwind text colour class per tone (written out so Tailwind sees them). */
export const TONE_TEXT: Record<StatusTone, string> = {
  neutral: 'text-status-planned',
  progress: 'text-status-progress',
  blocked: 'text-status-blocked',
  risk: 'text-status-risk',
  done: 'text-status-done',
  review: 'text-status-review',
  cancelled: 'text-status-cancelled',
}

/** Icon-chip tint (background and text) per tone, for stat tiles. */
export const TONE_TINT: Record<StatusTone, string> = {
  neutral: 'bg-line text-muted-ink',
  progress: 'bg-tint-progress text-status-progress',
  blocked: 'bg-tint-blocked text-status-blocked',
  risk: 'bg-tint-risk text-status-risk',
  done: 'bg-tint-done text-status-done',
  review: 'bg-inset text-status-review',
  cancelled: 'bg-inset text-status-cancelled',
}

/** Donut segment colours per task status (CSS colour values). */
export const TASK_SEGMENT_COLOR: Record<TaskStatus, string> = {
  inbox: '#8b8b9e',
  planned: '#a3a3b5',
  'in-progress': '#6ea8ff',
  blocked: '#ff7d73',
  review: '#d2a6ff',
  done: '#5ed39a',
  cancelled: '#4a4a5c',
}

export function isTaskStatus(value: string | null | undefined): value is TaskStatus {
  return (TASK_STATUSES as readonly string[]).includes(value ?? '')
}

import { STATUS_VOCABULARY, type NoteSummary } from '@/api/types'

export const LESSON_STATUSES = STATUS_VOCABULARY.lesson
/** Decision groups in reading order: what still needs a decision comes first. */
export const DECISION_STATUSES = STATUS_VOCABULARY.decision

/** What the Knowledge and Decisions URLs hold. `project` is the context switcher's parameter. */
export interface ListView {
  project?: string
  tag?: string
  /** A status of the page's vocabulary; undefined is all. */
  status?: string
  /** Vault path of the note open in the split pane. */
  note?: string
}

/** A `status` outside the page's vocabulary is ignored, so a stale link shows everything rather than nothing. */
export function parseListParams(params: URLSearchParams, vocabulary: readonly string[]): ListView {
  const status = params.get('status')
  return {
    project: params.get('project') || undefined,
    tag: params.get('tag') || undefined,
    status: status && vocabulary.includes(status) ? status : undefined,
    note: params.get('note') || undefined,
  }
}

/** Sets or clears one parameter and leaves the rest (the project context, the open note) alone. */
export function withParam(params: URLSearchParams, key: keyof ListView, value: string | undefined): URLSearchParams {
  const next = new URLSearchParams(params)
  if (value) next.set(key, value)
  else next.delete(key)
  return next
}

export const byModifiedDesc = (a: NoteSummary, b: NoteSummary) => b.modified.localeCompare(a.modified) || a.path.localeCompare(b.path)

export function filterLessons(lessons: NoteSummary[], view: ListView, { ignoreStatus = false } = {}): NoteSummary[] {
  return lessons
    .filter((n) => !view.project || n.project === view.project)
    .filter((n) => !view.tag || n.tags.includes(view.tag))
    .filter((n) => ignoreStatus || !view.status || n.status === view.status)
    .sort(byModifiedDesc)
}

/** Decisions under the project filter, with `status` applied unless `ignoreStatus` (the segment counts). */
export function filterDecisions(decisions: NoteSummary[], view: ListView, { ignoreStatus = false } = {}): NoteSummary[] {
  return decisions
    .filter((n) => !view.project || n.project === view.project)
    .filter((n) => ignoreStatus || !view.status || n.status === view.status)
    .sort(byModifiedDesc)
}

export interface DecisionGroup {
  key: string
  label: string
  decisions: NoteSummary[]
}

/** One group per vocabulary status that has decisions, `proposed` first; a status outside the vocabulary (or none) goes last. */
export function groupDecisions(decisions: NoteSummary[]): DecisionGroup[] {
  const known: readonly string[] = DECISION_STATUSES
  const groups: DecisionGroup[] = DECISION_STATUSES.map((s) => ({ key: s, label: s, decisions: decisions.filter((d) => d.status === s) }))
  const other = decisions.filter((d) => !d.status || !known.includes(d.status))
  if (other.length) groups.push({ key: 'other', label: 'No recognised status', decisions: other })
  return groups.filter((g) => g.decisions.length > 0).map((g) => ({ ...g, label: g.label[0].toUpperCase() + g.label.slice(1) }))
}

/** The tags present on the lessons, alphabetical. */
export const tagsOf = (lessons: NoteSummary[]): string[] => [...new Set(lessons.flatMap((n) => n.tags))].sort((a, b) => a.localeCompare(b))

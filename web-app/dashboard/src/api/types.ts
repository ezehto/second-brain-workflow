import type { components } from './generated/schema'

/**
 * The shapes of the API. Request and response shapes are the generated ones
 * (`generated/schema.d.ts`, from `web-app/backend/openapi.yaml`): this file
 * names them, keeps the constants the UI needs (vocabularies, sections) and
 * keeps a few narrower request types that the generated ones accept. Nullable
 * fields are `null`, never missing: the UI shows `N/A` for them.
 */
type Schemas = components['schemas']

export type NoteType = 'task' | 'project' | 'decision' | 'lesson' | 'capture' | 'daily' | 'note' | (string & {})

/** Task statuses, fixed by the design (plan section 2.3). */
export const TASK_STATUSES = ['inbox', 'planned', 'in-progress', 'blocked', 'review', 'done', 'cancelled'] as const
export type TaskStatus = (typeof TASK_STATUSES)[number]

/** Status vocabulary per type (plan section 2.3). Other types have none enforced. */
export const STATUS_VOCABULARY = {
  task: TASK_STATUSES,
  project: ['active', 'paused', 'done', 'archived'],
  decision: ['proposed', 'accepted', 'superseded', 'rejected'],
  lesson: ['active', 'archived'],
  capture: ['inbox', 'triaged', 'dismissed'],
} as const
export type VocabularyType = keyof typeof STATUS_VOCABULARY
export type StatusOf<T extends VocabularyType> = (typeof STATUS_VOCABULARY)[T][number]
/** Every status word of every vocabulary. */
export type VocabularyStatus = StatusOf<VocabularyType>

/** Status given to a new note of each type (plan section 2.3). */
export const DEFAULT_STATUS: { [T in VocabularyType]: StatusOf<T> } = {
  task: 'planned',
  project: 'active',
  decision: 'proposed',
  lesson: 'active',
  capture: 'inbox',
}

export type Priority = 'high' | 'medium' | 'low'

/** Promoted fields of one indexed note. `type` and `priority` are free text on the wire (stored as written). */
export type NoteSummary = Schemas['NoteSummary']
/** `GET /api/notes/lookup/`: one note in full. */
export type NoteDetail = Schemas['NoteDetail']

/** A page of a DRF list. The generated list type marks `next`/`previous` optional; the HTTP client always fills them. */
export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface NoteListParams {
  type?: NoteType
  status?: string[]
  priority?: Priority
  project?: string
  tag?: string
  due_before?: string
  due_after?: string
  overdue?: boolean
  path_prefix?: string
  has_parse_error?: boolean
  ordering?: '-modified' | 'due' | 'title' | 'path' | '-path'
  page?: number
  page_size?: number
}

/** `GET /api/projects/`: a project note with its slug and open-task count. */
export type ProjectSummary = Schemas['ProjectSummary']
export type IndexSummary = Schemas['IndexSummary']
/** `GET /api/dashboard/`. `today` is the vault's day (honours the test clock). */
export type DashboardResponse = Schemas['Dashboard']

export type IndexProblem = Schemas['IndexProblem']

export const INDEX_PROBLEM_CATEGORIES = [
  'parse_errors',
  'missing_ids',
  'duplicate_ids',
  'ambiguous_links',
  'unknown_project_slugs',
  'duplicate_project_slugs',
  'unknown_statuses',
  'invalid_dates',
] as const satisfies readonly IndexProblemCategory[]
export type IndexProblemCategory = keyof Schemas['IndexProblems']

/** `GET /api/index/status/`. */
export type IndexStatus = Schemas['IndexStatus']
/** `POST /api/index/refresh/`: the pass summary (not an `IndexStatus`). */
export type RefreshSummary = Schemas['RefreshSummary']

export type SearchResult = Schemas['SearchResult']
export type SearchResponse = Schemas['SearchResponse']

export const STANDUP_SECTIONS = [
  'Done',
  'Today',
  'Blockers',
  'Decisions / Updates',
  'Follow-ups',
  'Related Tasks / Projects',
] as const satisfies readonly StandupSection[]
export type StandupSection = Schemas['SectionEnum']

/** Where a wikilink target resolves: one note, several, or none (review O-7). */
export type LinkState = Schemas['StateEnum']

/** `GET /api/projects/{slug}/`. */
export type ProjectDetail = Schemas['ProjectDetail']

/** The six standup sections as lines of Markdown. */
export type StandupPreview = Schemas['StandupPreview']

/**
 * `GET /api/standups/today/`: today's daily note, or (404 on the wire) the
 * carry-forward preview of what starting the standup would write.
 */
export type StandupToday = Schemas['StandupToday']

/** `POST /api/standups/today/`. `created` is true on 201; `filled` says whether an untouched note was filled. */
export type StartStandupResponse = Schemas['StartStandupResponse']

/**
 * `POST /api/standups/today/append/`. `text` is the bare line: the writer adds
 * the list marker by the section's rule, so a caller never includes `- ` or `- [ ] `.
 */
export type AppendStandupRequest = Schemas['AppendStandupRequest']
/** The note and whether the section heading had to be added. */
export type AppendStandupResponse = Schemas['AppendStandupResponse']

/** The types `POST /api/notes/` can create (C17). */
export type CreatableType = Schemas['TypeEnum']

/** `POST /api/notes/` (C17): the generated request narrowed so a status belongs to the type's vocabulary. */
export type CreateNoteRequest = {
  [T in CreatableType]: {
    type: T
    title: string
    /** Project slug or title. */
    project?: string
    priority?: Priority
    due?: string
    status?: StatusOf<T>
    body?: string
  }
}[CreatableType]

/** `POST /api/notes/status/` (C17). `status` is a word the UI offers; the server checks it against the note's type and answers 422 when it is not in the vocabulary. */
export type StatusChangeRequest = Omit<Schemas['StatusChangeRequest'], 'status'> & { status: string }

export type TriageAction = Schemas['ActionEnum']

/** `POST /api/captures/triage/` (C17). `classification` is any kind the user chose (the server checks it), and is optional. */
export type TriageRequest = Omit<Schemas['TriageRequest'], 'classification'> & { classification?: string }
export type TriageResponse = Schemas['TriageResponse']

export type LoginRequest = Schemas['LoginRequest']
/** `GET /api/auth/me/`. */
export type Me = Schemas['Me']
/** `GET /api/health/`. */
export type Health = Schemas['Health']

/**
 * The body of a 4xx/5xx response. `candidates` lists the paths a `?id=` lookup
 * matched (409); `created_target` is the new note's path when a triage created
 * its target but could not edit the capture.
 */
export interface ApiErrorBody {
  detail: string
  candidates?: string[]
  created_target?: string
}

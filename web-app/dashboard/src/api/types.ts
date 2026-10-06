/**
 * PROVISIONAL until the OpenAPI contract (P1-24): every shape in this file is
 * hand-written from docs/plan/phase-1-foundation.md section 5 and may change
 * when `web-app/backend/openapi.yaml` exists. Then it is replaced by generated
 * types and this file shrinks to re-exports. Nullable fields are `null`, never
 * missing: the UI shows `N/A` for them.
 *
 * Provisional contract change: `TriageRequest.classification` is optional, and
 * sent only for `dismiss` when a classification was already written to the
 * capture (a kind merely chosen in the UI is not sent).
 */

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

/** Promoted fields of one indexed note, as listed by `GET /api/notes/`. */
export interface NoteSummary {
  /** The `id` frontmatter value; null for a note made by hand without one. */
  id: string | null
  /** Vault-relative path, e.g. `02-Work/Tasks/Fix N+1 query.md`. */
  path: string
  type: NoteType
  title: string
  /** Stored as written: any value, even one outside the type's vocabulary. */
  status: string | null
  priority: Priority | null
  /** Project slug as written in frontmatter. */
  project: string | null
  /** `YYYY-MM-DD`, or null when absent or unreadable. */
  due: string | null
  blocked_by: string | null
  /** Decisions: `YYYY-MM-DD` set when the status became accepted. */
  decided: string | null
  tags: string[]
  created: string | null
  /** Local ISO time with the vault offset, e.g. `2026-10-06T11:20:00+08:00`. */
  modified: string
  parse_error: string | null
}

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
export interface ProjectSummary {
  slug: string
  title: string
  path: string
  status: string | null
  goal: string | null
  open_task_count: number
  modified: string
}

export interface IndexSummary {
  /** Local ISO time of the last sync pass; null before the first pass. */
  last_pass_at: string | null
  problem_count: number
}

/** `GET /api/dashboard/`. */
export interface DashboardResponse {
  /** The vault's "today", `YYYY-MM-DD` (honours the test clock). */
  today: string
  today_tasks: NoteSummary[]
  in_progress: NoteSummary[]
  blocked: NoteSummary[]
  overdue: NoteSummary[]
  standup: StandupToday
  recent_activity: NoteSummary[]
  active_projects: ProjectSummary[]
  inbox_count: number
  index: IndexSummary
}

export interface IndexProblem {
  path: string
  detail: string
}

export const INDEX_PROBLEM_CATEGORIES = [
  'parse_errors',
  'missing_ids',
  'duplicate_ids',
  'ambiguous_links',
  'unknown_project_slugs',
  'duplicate_project_slugs',
  'unknown_statuses',
  'invalid_dates',
] as const
export type IndexProblemCategory = (typeof INDEX_PROBLEM_CATEGORIES)[number]

/** `GET /api/index/status/`. */
export interface IndexStatus {
  last_pass_at: string | null
  duration_ms: number | null
  counts_by_type: Record<string, number>
  problems: Record<IndexProblemCategory, IndexProblem[]>
  /** The pinned date when plan section 2.12 test mode is on. */
  test_mode: { today: string } | null
}

/**
 * `GET /api/search/?q=`. Provisional: results should also carry `project` (the
 * note's project slug or null) so a project context can filter them without
 * loading every note, and `snippet` should be plain text, not HTML.
 */
export interface SearchResult {
  path: string
  type: NoteType
  title: string
  snippet: string
  source: 'vault'
}
export interface SearchResponse {
  query: string
  results: SearchResult[]
}

export const STANDUP_SECTIONS = [
  'Done',
  'Today',
  'Blockers',
  'Decisions / Updates',
  'Follow-ups',
  'Related Tasks / Projects',
] as const
export type StandupSection = (typeof STANDUP_SECTIONS)[number]

/** Where a wikilink target resolves: one note, several, or none (review O-7). */
export type LinkState = 'resolved' | 'ambiguous' | 'unresolved'

/** `GET /api/notes/lookup/`: one note in full. */
export interface NoteDetail extends NoteSummary {
  frontmatter: Record<string, unknown>
  body: string
  content_hash: string
  /** Notes that link here. */
  backlinks: { path: string; title: string }[]
  /** Each link target as written in the body, to where it resolves. */
  links: Record<string, { path: string | null; state: LinkState }>
}

/** `GET /api/projects/{slug}/`. */
export interface ProjectDetail {
  project: ProjectSummary
  note: NoteDetail
  open_tasks: NoteSummary[]
  decisions: NoteSummary[]
  /** By modified time, then path. */
  recent_notes: NoteSummary[]
}

/** The six standup sections as lines of Markdown. */
export type StandupPreview = Record<StandupSection, string[]>

/**
 * `GET /api/standups/today/`: today's daily note, or (404 on the wire) the
 * carry-forward preview of what starting the standup would write.
 */
export type StandupToday =
  | { exists: true; note: NoteDetail; untouched: boolean }
  | { exists: false; preview: StandupPreview }

/**
 * `POST /api/standups/today/`. `created` is true on 201 (a new note with
 * carry-forward). Otherwise 200: `filled` says whether an untouched note was
 * filled (true) or a touched one returned unchanged (false). When `created`,
 * `filled` is true.
 */
export interface StartStandupResponse {
  created: boolean
  filled: boolean
  note: NoteDetail
  untouched: boolean
}

/**
 * `POST /api/standups/today/append/`. `text` is the bare line: the writer adds
 * the list marker by the section's rule (`- [ ] ` under Today and Follow-ups,
 * `- ` elsewhere), so a caller never includes `- ` or `- [ ] `.
 */
export interface AppendStandupRequest {
  section: StandupSection
  text: string
  expected_hash: string
}

/** The types `POST /api/notes/` can create (C17). */
export type CreatableType = 'task' | 'project' | 'decision' | 'lesson'

/** `POST /api/notes/` (C17). The status, when given, is from the type's vocabulary. */
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

/** `POST /api/notes/status/` (C17). */
export interface StatusChangeRequest {
  path: string
  status: string
  expected_hash: string
  /** Appended under `## Notes` when the status becomes `done`. */
  evidence?: string
}

export type TriageAction = 'task' | 'decision' | 'lesson' | 'project' | 'keep' | 'dismiss'

/** `POST /api/captures/triage/` (C17). */
export interface TriageRequest {
  path: string
  expected_hash: string
  action: TriageAction
  /** Required for every action but `dismiss`, which may omit it (provisional, see the note at the top). */
  classification?: string
  title?: string
  project?: string
  /** Retry after a partial failure: reuse this note instead of creating one. */
  existing_target?: string
}
export interface TriageResponse {
  capture: NoteDetail
  /** The note created or reused; null for `keep` and `dismiss`. */
  target: NoteSummary | null
}

export interface LoginRequest {
  username: string
  password: string
}
/** `GET /api/auth/me/`. */
export interface Me {
  username: string
}
/** `GET /api/health/`. */
export interface Health {
  status: 'ok'
}

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

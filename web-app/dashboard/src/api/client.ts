import type {
  ApiErrorBody,
  AppendStandupRequest,
  CreateNoteRequest,
  DashboardResponse,
  Health,
  IndexStatus,
  LoginRequest,
  Me,
  NoteDetail,
  NoteListParams,
  NoteSummary,
  Paginated,
  ProjectDetail,
  ProjectSummary,
  SearchResponse,
  StandupToday,
  StartStandupResponse,
  StatusChangeRequest,
  TriageRequest,
  TriageResponse,
} from './types'

/**
 * A failed API call. `status` is the HTTP status (409 collision or stale
 * hash, 422 invalid, ...). `body` carries the extra fields of the error body:
 * `candidates` for an ambiguous lookup, `created_target` for a partial triage.
 */
export class ApiError extends Error {
  readonly status: number
  readonly body: ApiErrorBody
  constructor(status: number, message: string, extra: Omit<ApiErrorBody, 'detail'> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = { detail: message, ...extra }
  }
}

/**
 * Everything the UI may ask of the backend: every endpoint of plan section 5,
 * one method each. Pages depend on this, never on an implementation. Add to
 * it here, not in a page.
 */
export interface ApiClient {
  // auth
  /** `GET /api/auth/csrf/`: sets the CSRF cookie. */
  csrf(): Promise<void>
  login(input: LoginRequest): Promise<Me>
  logout(): Promise<void>
  me(): Promise<Me>
  health(): Promise<Health>

  // notes
  listNotes(params?: NoteListParams): Promise<Paginated<NoteSummary>>
  /** `GET /api/notes/lookup/`. An `id` matching several notes rejects with 409 and `body.candidates`. */
  lookupNote(by: { path: string } | { id: string }): Promise<NoteDetail>
  /** `POST /api/notes/`. Rejects 409 on a name collision, 422 for an unknown project. */
  createNote(input: CreateNoteRequest): Promise<NoteSummary>
  /** `POST /api/notes/status/`. Rejects 409 on a stale `expected_hash`, 422 on a status outside the vocabulary. */
  changeStatus(input: StatusChangeRequest): Promise<NoteDetail>

  // captures
  createCapture(input: { text: string }): Promise<NoteSummary>
  /** `POST /api/captures/triage/`. On a partial failure rejects with `body.created_target` set. */
  triageCapture(input: TriageRequest): Promise<TriageResponse>

  // projects
  listProjects(): Promise<ProjectSummary[]>
  /** Rejects 404 for an unknown slug. */
  getProject(slug: string): Promise<ProjectDetail>

  // standups
  getStandupToday(): Promise<StandupToday>
  startStandup(): Promise<StartStandupResponse>
  appendToStandup(input: AppendStandupRequest): Promise<NoteDetail>

  // aggregates, search, index
  getDashboard(): Promise<DashboardResponse>
  search(query: string): Promise<SearchResponse>
  getIndexStatus(): Promise<IndexStatus>
  refreshIndex(): Promise<IndexStatus>
}

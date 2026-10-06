import { ApiError, type ApiClient } from './client'
import type {
  ApiErrorBody,
  AppendStandupResponse,
  DashboardResponse,
  Health,
  IndexStatus,
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
  TriageResponse,
} from './types'

const API_BASE = '/api'
const CSRF_COOKIE = 'csrftoken'
const CSRF_HEADER = 'X-CSRFToken'
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

/** Value of the `csrftoken` cookie, or null when the browser has none. */
export function readCsrfCookie(): string | null {
  if (typeof document === 'undefined') return null
  for (const part of document.cookie.split(';')) {
    const [name, ...value] = part.trim().split('=')
    if (name !== CSRF_COOKIE) continue
    try {
      return decodeURIComponent(value.join('='))
    } catch {
      return null // a malformed cookie is as good as none: the next request asks for a fresh one
    }
  }
  return null
}

export interface HttpClientOptions {
  /** Injected so a test can stand in for the network. Defaults to the global `fetch`. */
  fetch?: typeof fetch
}

type Query = Record<string, string | number | boolean | string[] | undefined>

function queryString(params: Query): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) continue
    if (Array.isArray(value)) value.forEach((v) => search.append(key, v))
    else search.append(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

const THROTTLED = 'Too many attempts. Wait a minute, then try again.'

/**
 * The real `ApiClient`: JSON over `fetch` to `/api`, which the dev server proxies to Django.
 *
 * - Cookies travel with `credentials: 'same-origin'`; the session cookie is HttpOnly, so
 *   nothing here ever reads it.
 * - Unsafe methods send `X-CSRFToken` taken from the `csrftoken` cookie, read at the moment of
 *   the request (Django rotates the token at login). A GET never sends it. When the cookie is
 *   missing, `GET /api/auth/csrf/` is called first.
 * - A CSRF failure (403 "CSRF failed.") on an unsafe method fetches a fresh cookie and retries once.
 * - A 4xx/5xx body `{detail, candidates?, created_target?}` becomes an `ApiError` with the
 *   status and that body.
 * - 401, and 403 other than a CSRF failure, from anything but login mean the session is gone:
 *   listeners (the session provider) are told, and the call still rejects.
 */
export function createHttpClient(options: HttpClientOptions = {}): ApiClient {
  const doFetch: typeof fetch = options.fetch ?? ((input, init) => fetch(input, init))
  const listeners = new Set<() => void>()

  async function send(method: string, path: string, body?: unknown, query?: Query, init: { session?: boolean; retried?: boolean } = {}): Promise<Response> {
    const unsafe = UNSAFE_METHODS.has(method)
    if (unsafe && !readCsrfCookie()) await send('GET', '/auth/csrf/', undefined, undefined, { session: false })
    const headers: Record<string, string> = { Accept: 'application/json' }
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    if (unsafe) {
      const token = readCsrfCookie()
      if (token) headers[CSRF_HEADER] = token
    }
    let response: Response
    try {
      response = await doFetch(`${API_BASE}${path}${query ? queryString(query) : ''}`, {
        method,
        headers,
        credentials: 'same-origin',
        body: body === undefined ? undefined : JSON.stringify(body),
      })
    } catch {
      throw new ApiError(0, 'Cannot reach the server. Check that the backend is running, then try again.')
    }
    if (response.ok) return response

    const error = await toError(response)
    const csrfFailure = response.status === 403 && /^csrf failed/i.test(error.message)
    if (csrfFailure && unsafe && !init.retried) {
      // Django rejected the token before the view ran, so nothing was done: take a fresh cookie and send once more.
      await send('GET', '/auth/csrf/', undefined, undefined, { session: false })
      return send(method, path, body, query, { ...init, retried: true })
    }
    const sessionGone = (response.status === 401 || (response.status === 403 && !csrfFailure)) && init.session !== false
    if (sessionGone) listeners.forEach((listener) => listener())
    throw error
  }

  async function json<T>(method: string, path: string, body?: unknown, query?: Query, init?: { session?: boolean }): Promise<T> {
    const response = await send(method, path, body, query, init)
    return (await response.json()) as T
  }

  return {
    onUnauthenticated(listener) {
      listeners.add(listener)
      return () => void listeners.delete(listener)
    },

    async csrf() {
      await send('GET', '/auth/csrf/', undefined, undefined, { session: false })
    },
    // Login answers 400/403/429 about the credentials, never "session gone".
    login: (input) => json<Me>('POST', '/auth/login/', input, undefined, { session: false }),
    async logout() {
      await send('POST', '/auth/logout/')
    },
    me: () => json<Me>('GET', '/auth/me/'),
    // 503 carries the same body with `status: "error"`.
    async health() {
      try {
        return await json<Health>('GET', '/health/', undefined, undefined, { session: false })
      } catch (error) {
        if (error instanceof ApiError && error.status === 503) return { status: 'error' }
        throw error
      }
    },

    async listNotes(params: NoteListParams = {}) {
      const page = await json<Paginated<NoteSummary>>('GET', '/notes/', undefined, { ...params })
      return { count: page.count, next: page.next ?? null, previous: page.previous ?? null, results: page.results }
    },
    lookupNote: (by) => json<NoteDetail>('GET', '/notes/lookup/', undefined, by),
    createNote: (input) => json<NoteSummary>('POST', '/notes/', input),
    changeStatus: (input) => json<NoteDetail>('POST', '/notes/status/', input),

    createCapture: (input) => json<NoteSummary>('POST', '/captures/', input),
    triageCapture: (input) => json<TriageResponse>('POST', '/captures/triage/', input),

    listProjects: () => json<ProjectSummary[]>('GET', '/projects/'),
    getProject: (slug) => json<ProjectDetail>('GET', `/projects/${encodeURIComponent(slug)}/`),

    async getStandupToday() {
      try {
        return await json<StandupToday>('GET', '/standups/today/')
      } catch (error) {
        // No daily note yet: the 404 body is the carry-forward preview.
        if (error instanceof ApiError && error.status === 404 && 'preview' in error.body) {
          return { exists: false, preview: (error.body as unknown as { preview: StandupPreviewBody }).preview }
        }
        throw error
      }
    },
    startStandup: () => json<StartStandupResponse>('POST', '/standups/today/', {}),
    appendToStandup: (input) => json<AppendStandupResponse>('POST', '/standups/today/append/', input),

    getDashboard: () => json<DashboardResponse>('GET', '/dashboard/'),
    async search(query) {
      // The API answers 400 for a blank `q`; nothing to look for is an empty result.
      if (!query.trim()) return { query, results: [] } satisfies SearchResponse
      return json<SearchResponse>('GET', '/search/', undefined, { q: query })
    },
    getIndexStatus: () => json<IndexStatus>('GET', '/index/status/'),
    async refreshIndex() {
      // The pass summary is not what the page shows; the status after the pass is.
      await send('POST', '/index/refresh/', {})
      return json<IndexStatus>('GET', '/index/status/')
    },
  }
}

type StandupPreviewBody = Extract<StandupToday, { exists: false }>['preview']

/** An `ApiError` from a failed response: `{detail, ...}` when the body is JSON, a plain sentence when it is not. */
async function toError(response: Response): Promise<ApiError> {
  let body: Record<string, unknown> = {}
  try {
    const parsed: unknown = await response.json()
    if (parsed && typeof parsed === 'object') body = parsed as Record<string, unknown>
  } catch {
    // HTML from a proxy or a crashed server: the status is all there is.
  }
  const { detail, ...extra } = body
  const message =
    response.status === 429
      ? THROTTLED
      : typeof detail === 'string' && detail
        ? detail
        : response.status >= 500
          ? 'The server could not complete the request. Try again in a moment.'
          : `The request failed (${response.status}).`
  return new ApiError(response.status, message, extra as Omit<ApiErrorBody, 'detail'>)
}

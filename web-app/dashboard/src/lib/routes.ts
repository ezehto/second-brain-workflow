/** Every link the dashboard makes goes through here, so a page can be built later without touching callers. */

export const routes = {
  dashboard: '/',
  standups: '/standups',
  inbox: '/inbox',
  tasks: '/tasks',
  projects: '/projects',
  workflow: '/workflow',
  timeline: '/timeline',
  knowledge: '/knowledge',
  decisions: '/decisions',
  upskilling: '/upskilling',
  search: '/search',
  indexStatus: '/index-status',
  login: '/login',
} as const

/** The note reader (P1-32). The vault path is the stable identity of a note. */
export const noteHref = (path: string) => `/notes?path=${encodeURIComponent(path)}`

export const projectHref = (slug: string) => `/projects/${encodeURIComponent(slug)}`

/**
 * Task list URL contract (the Tasks page reads these query parameters):
 * - `status`: a task status, or `open` for every status except done and cancelled
 * - `today=true`: the standup carry-forward set (in progress, in review, and
 *   planned tasks due today or earlier), the list the "For today" tile counts
 * - `overdue=true`: open tasks due before today
 * - `priority`, `project` (slug): exact match
 * - `project` also becomes the context switcher's filter on every page (not built yet)
 */
export interface TaskFilters {
  status?: 'open' | string
  today?: boolean
  priority?: string
  project?: string
  overdue?: boolean
}
export function tasksHref(filters: TaskFilters = {}): string {
  const q = new URLSearchParams()
  if (filters.status) q.set('status', filters.status)
  if (filters.priority) q.set('priority', filters.priority)
  if (filters.project) q.set('project', filters.project)
  if (filters.today) q.set('today', 'true')
  if (filters.overdue) q.set('overdue', 'true')
  const s = q.toString()
  return s ? `${routes.tasks}?${s}` : routes.tasks
}

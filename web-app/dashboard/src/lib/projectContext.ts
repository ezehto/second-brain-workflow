import { useMemo } from 'react'
import { useSearchParams } from 'react-router'
import { noteHref, projectHref, tasksHref, type TaskFilters } from './routes'

/** The project context filter lives in this query parameter on every page (decision 2). */
export const PROJECT_PARAM = 'project'

/** The slug of the selected project, or null for "All projects". */
export function useProjectContext(): string | null {
  const [params] = useSearchParams()
  return params.get(PROJECT_PARAM)
}

/**
 * Adds the project context to an internal link so it survives navigation. A
 * link that already names a project keeps its own (a project's tasks link).
 */
export function withProject(href: string, project: string | null): string {
  if (!project) return href
  const [path, query = ''] = href.split('?')
  const params = new URLSearchParams(query)
  if (!params.has(PROJECT_PARAM)) params.set(PROJECT_PARAM, project)
  return `${path}?${params.toString()}`
}

/**
 * The link helpers of `lib/routes.ts`, with the current project context added
 * so it survives navigation. Every internal link in a page or shared component
 * goes through this hook; `link(href)` wraps any other href (`routes.x`).
 */
export function useProjectHref() {
  const project = useProjectContext()
  return useMemo(
    () => ({
      link: (href: string) => withProject(href, project),
      note: (path: string) => withProject(noteHref(path), project),
      project: (slug: string) => withProject(projectHref(slug), project),
      tasks: (filters?: TaskFilters) => withProject(tasksHref(filters), project),
    }),
    [project],
  )
}

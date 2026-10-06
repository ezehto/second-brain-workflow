import { useSearchParams } from 'react-router'

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

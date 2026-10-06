import type { NoteDetail, NoteSummary, ProjectSummary } from '@/api/types'
import type { DailyLine } from '@/domain/daily'
import { noteHref, projectHref } from '@/lib/routes'

export interface LinkTarget {
  kind: 'project' | 'note'
  href: string
}

export interface LinkResolver {
  /** Where a wikilink goes: a project through `projectHref`, any other note through `noteHref`; null when it resolves to nothing. */
  resolve: (target: string) => LinkTarget | null
  /** The project slug of a line, through the first link that is a project or a task with a project. */
  projectOf: (line: DailyLine) => string | null
  /** The project's title for a slug, or null when it is not in the project list. */
  projectTitle: (slug: string) => string | null
}

/**
 * Resolves wikilinks by title against the project list, the note's own
 * resolved links (when a note is open) and the task list. A link that matches
 * none of them is shown as text, not as a dead link.
 */
export function linkResolver(projects: ProjectSummary[], tasks: NoteSummary[], note?: NoteDetail): LinkResolver {
  const bySlugTitle = new Map(projects.map((p) => [p.title.toLowerCase(), p]))
  const taskByTitle = new Map(tasks.map((t) => [t.title.toLowerCase(), t]))
  const own = new Map(Object.entries(note?.links ?? {}).map(([target, link]) => [target.toLowerCase(), link]))
  const bySlug = new Map(projects.map((p) => [p.slug, p.title]))
  return {
    projectTitle: (slug) => bySlug.get(slug) ?? null,
    resolve: (target) => {
      const key = target.toLowerCase()
      const project = bySlugTitle.get(key)
      if (project) return { kind: 'project', href: projectHref(project.slug) }
      const path = own.get(key)?.path ?? taskByTitle.get(key)?.path
      return path ? { kind: 'note', href: noteHref(path) } : null
    },
    projectOf: (line) => {
      for (const target of line.links) {
        const key = target.toLowerCase()
        const project = bySlugTitle.get(key)?.slug ?? taskByTitle.get(key)?.project
        if (project) return project
      }
      return null
    },
  }
}

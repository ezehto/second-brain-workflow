import type { NoteDetail, NoteSummary, ProjectSummary } from '@/api/types'
import type { DailyLine } from '@/domain/daily'
import { noteHref, projectHref } from '@/lib/routes'

/** Where a wikilink goes, or why it goes nowhere. `unknown` means it could not be told (no server answer and no title match). */
export type Resolution = { kind: 'project' | 'note'; href: string } | { kind: 'ambiguous' | 'unresolved' | 'unknown' }

export interface LinkResolver {
  /**
   * For a line of the note on screen: the API's own answer (`note.links`) and
   * nothing else, so a link never goes anywhere the server did not resolve.
   * Without an open note (the not-yet-written preview) it falls back to titles.
   */
  resolve: (target: string) => Resolution
  /**
   * For a line of any other note (Yesterday, the patterns), which has no
   * `links` map in hand: a match on title against the project and task lists,
   * ambiguous when two notes share the title.
   */
  resolveByTitle: (target: string) => Resolution
  /** The project slug of a line, through the first link that is a project or a task with a project (by title). */
  projectOf: (line: DailyLine) => string | null
  /** The project's title for a slug, or null when it is not in the project list. */
  projectTitle: (slug: string) => string | null
}

function byTitle<T extends { title: string }>(items: T[]): Map<string, T[]> {
  const map = new Map<string, T[]>()
  for (const item of items) map.set(item.title.toLowerCase(), [...(map.get(item.title.toLowerCase()) ?? []), item])
  return map
}

export function linkResolver(projects: ProjectSummary[], tasks: NoteSummary[], note?: NoteDetail): LinkResolver {
  const projectsByTitle = byTitle(projects)
  const tasksByTitle = byTitle(tasks)
  const bySlug = new Map(projects.map((p) => [p.slug, p.title]))
  const projectByPath = new Map(projects.map((p) => [p.path, p]))
  const own = note ? new Map(Object.entries(note.links).map(([target, link]) => [target.toLowerCase(), link])) : null

  const hrefFor = (path: string): Resolution => {
    const project = projectByPath.get(path)
    return project ? { kind: 'project', href: projectHref(project.slug) } : { kind: 'note', href: noteHref(path) }
  }

  const resolveByTitle = (target: string): Resolution => {
    const key = target.toLowerCase()
    const hits = [...(projectsByTitle.get(key) ?? []), ...(tasksByTitle.get(key) ?? [])]
    if (hits.length > 1) return { kind: 'ambiguous' }
    if (hits.length === 0) return { kind: 'unknown' }
    return 'slug' in hits[0] ? { kind: 'project', href: projectHref(hits[0].slug) } : hrefFor(hits[0].path)
  }

  return {
    projectTitle: (slug) => bySlug.get(slug) ?? null,
    resolveByTitle,
    resolve: (target) => {
      if (!own) return resolveByTitle(target)
      const link = own.get(target.toLowerCase())
      if (!link || link.state === 'unresolved') return { kind: 'unresolved' }
      if (link.state === 'ambiguous' || !link.path) return { kind: 'ambiguous' }
      return hrefFor(link.path)
    },
    projectOf: (line) => {
      for (const target of line.links) {
        const key = target.toLowerCase()
        const project = projectsByTitle.get(key)?.[0]?.slug ?? tasksByTitle.get(key)?.[0]?.project
        if (project) return project
      }
      return null
    },
  }
}

import { NOT_AVAILABLE } from '@/lib/dates'
import type { ProjectSummary } from '@/api/types'

export interface ProjectLookup {
  /** Display name for a project slug: `N/A` for none, `x (unknown)` for a slug with no project note. */
  title: (slug: string | null) => string
  /** Whether the slug names a real project note (so a link to it will resolve). */
  known: (slug: string | null) => boolean
}

/**
 * Resolves slugs against the project list. While the list is still loading
 * (`undefined`) the slug is shown as written rather than flagged unknown.
 */
export function projectLookup(projects: ProjectSummary[] | undefined): ProjectLookup {
  const bySlug = new Map((projects ?? []).map((p) => [p.slug, p]))
  return {
    title: (slug) => {
      if (!slug) return NOT_AVAILABLE
      if (!projects) return slug
      return bySlug.get(slug)?.title ?? `${slug} (unknown)`
    },
    known: (slug) => !!slug && bySlug.has(slug),
  }
}

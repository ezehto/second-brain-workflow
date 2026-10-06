import { INDEX_PROBLEM_CATEGORIES, type IndexProblemCategory, type IndexStatus } from '@/api/types'

/**
 * Categories where the index cannot trust or tell notes apart: a note that
 * cannot be parsed, or two notes or projects that claim the same identity.
 * Every other category is a warning: the note is indexed and findable, but
 * something about it needs tidying.
 */
export const INDEX_ERROR_CATEGORIES: readonly IndexProblemCategory[] = ['parse_errors', 'duplicate_ids', 'duplicate_project_slugs']

const countIn = (status: IndexStatus, categories: readonly IndexProblemCategory[]) =>
  categories.reduce((n, key) => n + (status.problems[key]?.length ?? 0), 0)

/** Total problems across every category of the index status. */
export function indexProblemCount(status: IndexStatus): number {
  return countIn(status, INDEX_PROBLEM_CATEGORIES)
}

/** Problems in the error categories only; the header badge shows this and the rail keeps the total. */
export function indexErrorCount(status: IndexStatus): number {
  return countIn(status, INDEX_ERROR_CATEGORIES)
}

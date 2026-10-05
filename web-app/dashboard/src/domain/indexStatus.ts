import { INDEX_PROBLEM_CATEGORIES, type IndexStatus } from '@/api/types'

/** Total problems across every category of the index status. */
export function indexProblemCount(status: IndexStatus): number {
  return INDEX_PROBLEM_CATEGORIES.reduce((n, key) => n + (status.problems[key]?.length ?? 0), 0)
}

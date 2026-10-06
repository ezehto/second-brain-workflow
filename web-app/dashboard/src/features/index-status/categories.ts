import type { IndexProblemCategory } from '@/api/types'

/** What each problem category means, in the words the page shows. */
export const CATEGORY_LABELS: Record<IndexProblemCategory, string> = {
  parse_errors: 'Parse errors',
  missing_ids: 'Missing ids',
  duplicate_ids: 'Duplicate ids',
  ambiguous_links: 'Ambiguous links',
  unknown_project_slugs: 'Unknown project slugs',
  duplicate_project_slugs: 'Duplicate project slugs',
  unknown_statuses: 'Unknown statuses',
  invalid_dates: 'Invalid dates',
}

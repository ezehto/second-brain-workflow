import { describe, expect, it } from 'vitest'
import { INDEX_PROBLEM_CATEGORIES, type IndexStatus } from '@/api/types'
import { indexProblemFixtures } from '@/api/mock/fixtures'
import { INDEX_ERROR_CATEGORIES, indexErrorCount, indexProblemCount } from './indexStatus'

const status = (problems: IndexStatus['problems']): IndexStatus => ({ last_pass_at: null, duration_ms: null, counts_by_type: {}, problems, test_mode: null })
const none = () => Object.fromEntries(INDEX_PROBLEM_CATEGORIES.map((c) => [c, []])) as unknown as IndexStatus['problems']
const one = { path: 'a.md', detail: 'x' }

describe('index problem counts', () => {
  it('counts every category in the total and only error categories in the error count', () => {
    const s = status(indexProblemFixtures())
    expect(indexProblemCount(s)).toBe(8)
    expect(indexErrorCount(s)).toBe(2)
  })

  it('has no errors when only warnings exist, so the header badge stays hidden', () => {
    const s = status({ ...none(), ambiguous_links: [one], unknown_statuses: [one, one], invalid_dates: [one] })
    expect(indexProblemCount(s)).toBe(4)
    expect(indexErrorCount(s)).toBe(0)
  })

  it('treats parse errors and duplicate ids and project slugs as errors', () => {
    for (const category of INDEX_ERROR_CATEGORIES) expect(indexErrorCount(status({ ...none(), [category]: [one] }))).toBe(1)
  })
})

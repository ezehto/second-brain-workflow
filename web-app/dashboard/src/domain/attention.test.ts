import { describe, expect, it } from 'vitest'
import { task } from '@/test/notes'
import { attentionRows } from './attention'

describe('attentionRows', () => {
  const rows = attentionRows(
    [
      task('b', { status: 'blocked', blocked_by: 'infra', due: '2026-10-05', priority: 'high' }),
      task('r', { status: 'review' }),
      task('d', { status: 'done', priority: 'high' }),
    ],
    '2026-10-06',
  )
  const byKey = Object.fromEntries(rows.map((r) => [r.key, r]))

  it('has the five rows in order', () => {
    expect(rows.map((r) => r.key)).toEqual(['blocked', 'overdue', 'high-priority', 'in-review', 'incidents'])
  })
  it('counts blocked, overdue, open high-priority and in-review tasks', () => {
    expect(byKey.blocked.count).toBe(1)
    expect(byKey.overdue.count).toBe(1)
    expect(byKey['high-priority'].count).toBe(1)
    expect(byKey['in-review'].count).toBe(1)
  })
  it('gives incidents no count, so the page shows N/A', () => {
    expect(byKey.incidents.count).toBeNull()
    expect(byKey.incidents.to).toBeNull()
  })
})

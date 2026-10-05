import { describe, expect, it } from 'vitest'
import { task } from '@/test/notes'
import { countByStatus, countUnknownStatus, isOverdue } from './tasks'

describe('isOverdue', () => {
  it('is relative to the injected today', () => {
    const t = task('t', { due: '2026-10-05' })
    expect(isOverdue(t, '2026-10-06')).toBe(true)
    expect(isOverdue(t, '2026-10-05')).toBe(false)
    expect(isOverdue(t, '2026-10-04')).toBe(false)
  })
  it('is false without a due date', () => {
    expect(isOverdue(task('t'), '2026-10-06')).toBe(false)
  })
  it('is false once the task is done or cancelled', () => {
    expect(isOverdue(task('t', { due: '2026-10-01', status: 'done' }), '2026-10-06')).toBe(false)
    expect(isOverdue(task('t', { due: '2026-10-01', status: 'cancelled' }), '2026-10-06')).toBe(false)
  })
  it('counts a blocked or in-progress task as overdue', () => {
    expect(isOverdue(task('t', { due: '2026-10-01', status: 'blocked' }), '2026-10-06')).toBe(true)
  })
})

describe('countByStatus', () => {
  it('counts in vocabulary order and drops empty statuses', () => {
    const counts = countByStatus([task('a', { status: 'done' }), task('b', { status: 'planned' }), task('c', { status: 'done' })])
    expect(counts).toEqual([
      { status: 'planned', count: 1 },
      { status: 'done', count: 2 },
    ])
  })
  it('keeps statuses outside the vocabulary out of the counts and reports them', () => {
    const tasks = [task('a', { status: 'wip' }), task('b', { status: null }), task('c')]
    expect(countByStatus(tasks)).toEqual([{ status: 'planned', count: 1 }])
    expect(countUnknownStatus(tasks)).toBe(2)
  })
})

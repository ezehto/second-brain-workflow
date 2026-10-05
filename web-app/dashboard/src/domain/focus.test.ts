import { describe, expect, it } from 'vitest'
import { task } from '@/test/notes'
import { todaysFocus } from './focus'

const T = '2026-10-06'

describe('todaysFocus', () => {
  it('orders overdue, then blocked, then due today, then in review', () => {
    const focus = todaysFocus(
      [
        task('review', { status: 'review' }),
        task('today', { status: 'planned', due: T }),
        task('blocked', { status: 'blocked', blocked_by: 'infra' }),
        task('late', { status: 'planned', due: '2026-10-03' }),
      ],
      T,
    )
    expect(focus.map((f) => f.task.title)).toEqual(['late', 'blocked', 'today', 'review'])
    expect(focus.map((f) => f.rank)).toEqual([1, 2, 3, 4])
  })

  it('within a group puts high priority first, then the earliest due date', () => {
    const focus = todaysFocus(
      [
        task('low early', { due: '2026-10-01', priority: 'low' }),
        task('high late', { due: '2026-10-05', priority: 'high' }),
        task('high early', { due: '2026-10-02', priority: 'high' }),
        task('none', { due: '2026-10-01' }),
      ],
      T,
    )
    expect(focus.map((f) => f.task.title)).toEqual(['high early', 'high late', 'low early', 'none'])
  })

  it('shows at most five', () => {
    const many = Array.from({ length: 8 }, (_, i) => task(`t${i}`, { due: '2026-10-01' }))
    expect(todaysFocus(many, T)).toHaveLength(5)
  })

  it('leaves out done, cancelled and inbox tasks and tasks with nothing pressing', () => {
    const focus = todaysFocus(
      [
        task('done', { status: 'done', due: '2026-10-01' }),
        task('cancelled', { status: 'cancelled', due: '2026-10-01' }),
        task('inbox', { status: 'inbox', due: T }),
        task('later', { status: 'planned', due: '2026-10-20' }),
        task('no date'),
      ],
      T,
    )
    expect(focus).toEqual([])
  })

  it('states the reason, with the day count and the blocker', () => {
    const [a, b, c, d, e] = todaysFocus(
      [
        task('a', { due: '2026-10-05' }),
        task('b', { due: '2026-10-03', status: 'blocked', blocked_by: 'the provider' }),
        task('c', { status: 'blocked' }),
        task('d', { due: T, status: 'in-progress' }),
        task('e', { status: 'review' }),
      ],
      T,
    )
    const byTitle = Object.fromEntries([a, b, c, d, e].map((f) => [f.task.title, f.reason]))
    expect(byTitle.a).toBe('Overdue 1 day')
    expect(byTitle.b).toBe('Overdue 3 days, blocked: the provider')
    expect(byTitle.c).toBe('Blocked: N/A')
    expect(byTitle.d).toBe('Due today, in progress')
    expect(byTitle.e).toBe('In review')
  })

  it('ranks a priority outside high, medium and low after low instead of breaking the sort', () => {
    const odd = task('odd', { due: '2026-10-01', priority: 'urgent' as never })
    const focus = todaysFocus([odd, task('low', { due: '2026-10-02', priority: 'low' }), task('high', { due: '2026-10-03', priority: 'high' })], T)
    expect(focus.map((f) => f.task.title)).toEqual(['high', 'low', 'odd'])
  })
})

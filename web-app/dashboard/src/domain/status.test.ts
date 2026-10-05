import { describe, expect, it } from 'vitest'
import { TASK_STATUSES } from '@/api/types'
import { TASK_SEGMENT_COLOR, statusTone } from './status'

describe('statusTone', () => {
  it.each([
    ['in-progress', 'progress'],
    ['blocked', 'blocked'],
    ['review', 'review'],
    ['done', 'done'],
    ['accepted', 'done'],
    ['cancelled', 'cancelled'],
    ['planned', 'neutral'],
    ['inbox', 'neutral'],
    ['proposed', 'neutral'],
  ])('maps %s to %s', (status, tone) => {
    expect(statusTone(status)).toBe(tone)
  })
  it('treats a status outside the vocabularies, or none, as neutral', () => {
    expect(statusTone('wip')).toBe('neutral')
    expect(statusTone(null)).toBe('neutral')
  })
  it('has a donut colour for every task status', () => {
    for (const s of TASK_STATUSES) expect(TASK_SEGMENT_COLOR[s]).toMatch(/^#[0-9a-f]{6}$/)
  })
})

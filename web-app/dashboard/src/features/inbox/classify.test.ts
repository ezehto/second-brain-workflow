import { describe, expect, it } from 'vitest'
import type { NoteDetail } from '@/api/types'
import { CLASSIFICATIONS, actionLabel, captureText, capturedWhen, conversionOf } from './classify'

const note = (over: Partial<NoteDetail>) => ({ title: '2026-10-06 0912 todo: renew the staging TLS', body: '', modified: '2026-10-06T09:12:00+08:00', frontmatter: {}, ...over }) as NoteDetail

describe('classification mapping (plan 2.13)', () => {
  it('has the ten classifications', () => {
    expect(CLASSIFICATIONS).toHaveLength(10)
  })
  it.each([
    ['task', 'task', 'Create task'],
    ['problem', 'task', 'Create task'],
    ['decision', 'decision', 'Create decision'],
    ['learning-topic', 'lesson', 'Create lesson'],
    ['note', 'lesson', 'Create lesson'],
    ['project', 'project', 'Create project note'],
    ['ticket', null, 'Keep in inbox'],
    ['architecture-idea', null, 'Keep in inbox'],
    ['question', null, 'Keep in inbox'],
    ['thought', null, 'Keep in inbox'],
  ])('%s converts to %s, button "%s"', (kind, conversion, label) => {
    expect(conversionOf(kind)).toBe(conversion)
    expect(actionLabel(kind)).toBe(label)
  })
})

describe('capture text and time', () => {
  it('uses the first non-heading body line, else the file name without its prefix', () => {
    expect(captureText(note({ body: '\n## Notes\nFirst line\nsecond' }))).toBe('First line')
    expect(captureText(note({ body: '## Notes\n' }))).toBe('todo: renew the staging TLS')
  })
  it('shows the time for today and the date and time for older captures', () => {
    expect(capturedWhen(note({}), '2026-10-06')).toBe('09:12')
    expect(capturedWhen(note({}), '2026-10-07')).toBe('Oct 6, 09:12')
    expect(capturedWhen(note({ title: 'by hand' }), '2026-10-06')).toBe('09:12')
  })
})

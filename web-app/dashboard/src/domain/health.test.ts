import { describe, expect, it } from 'vitest'
import { task } from '@/test/notes'
import { projectHealth, projectProgress } from './health'

const T = '2026-10-06'
const active = { status: 'active' }

describe('projectHealth', () => {
  it('is Blocked when an open task is blocked, even if others are overdue', () => {
    const h = projectHealth(active, [task('a', { status: 'blocked' }), task('b', { due: '2026-10-01' })], T)
    expect(h).toMatchObject({ label: 'Blocked', tone: 'blocked', reason: '1 blocked task' })
  })
  it('is At risk with an overdue open task and none blocked', () => {
    const h = projectHealth(active, [task('a', { due: '2026-10-01' }), task('b', { due: '2026-10-02' })], T)
    expect(h).toMatchObject({ label: 'At risk', tone: 'risk', reason: '2 overdue open tasks' })
  })
  it('is On track with open tasks, none blocked or overdue', () => {
    const h = projectHealth(active, [task('a', { due: '2026-10-09' }), task('b')], T)
    expect(h).toMatchObject({ label: 'On track', tone: 'done', reason: '2 open, none blocked or overdue' })
  })
  it('is Completed when the project status is done, whatever its tasks say', () => {
    const h = projectHealth({ status: 'done' }, [task('a', { status: 'blocked' })], T)
    expect(h).toMatchObject({ label: 'Completed', tone: 'done' })
  })
  it('is Unknown with no tasks', () => {
    expect(projectHealth(active, [], T)).toMatchObject({ label: 'Unknown, insufficient data', reason: 'No tasks' })
  })
  it('is Unknown when every task is finished or dropped', () => {
    const h = projectHealth(active, [task('a', { status: 'done' }), task('b', { status: 'cancelled' })], T)
    expect(h).toMatchObject({ label: 'Unknown, insufficient data', reason: 'No open tasks' })
  })
  it('ignores a blocked task that is cancelled', () => {
    expect(projectHealth(active, [task('a', { status: 'cancelled' }), task('b')], T).label).toBe('On track')
  })
})

describe('projectProgress', () => {
  it('counts done of all non-cancelled tasks', () => {
    const p = projectProgress([task('a', { status: 'done' }), task('b'), task('c', { status: 'cancelled' })])
    expect(p).toEqual({ done: 1, total: 2, percent: 50, text: '1 of 2 done' })
  })
  it('is N/A when there is nothing to count', () => {
    expect(projectProgress([])).toMatchObject({ percent: null, text: 'N/A' })
    expect(projectProgress([task('a', { status: 'cancelled' })]).text).toBe('N/A')
  })
})

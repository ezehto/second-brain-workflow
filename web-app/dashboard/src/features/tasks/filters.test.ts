import { describe, expect, it } from 'vitest'
import { taskFixtures } from '@/api/mock/fixtures'
import { tasksHref, type TaskFilters } from '@/lib/routes'
import { task } from '@/test/notes'
import { isForToday } from '@/domain/tasks'
import { applyTaskFilters, buildTaskParams, parseTaskParams } from './filters'
import { compareTasks, groupTasks } from './grouping'
import { projectLookup } from '@/domain/projects'

const TODAY = '2026-10-06'
const tasks = taskFixtures()
const titles = (list: { title: string }[]) => list.map((t) => t.title)

describe('task URL contract', () => {
  const cases: TaskFilters[] = [
    {},
    { status: 'blocked' },
    { status: 'open', overdue: true },
    { today: true },
    { status: 'review', priority: 'high', project: 'ipp' },
  ]
  it.each(cases)('parses and builds the same query as tasksHref for %j', (filters) => {
    const query = tasksHref(filters).split('?')[1] ?? ''
    const view = parseTaskParams(new URLSearchParams(query))
    expect(view.filters).toEqual({ status: undefined, priority: undefined, project: undefined, today: undefined, overdue: undefined, ...filters })
    expect(buildTaskParams(view).toString()).toBe(query)
  })

  it('keeps group out of the URL when it is the default, and ignores unknown values', () => {
    expect(buildTaskParams({ filters: {}, group: 'project' }).toString()).toBe('')
    expect(buildTaskParams({ filters: { status: 'open' }, group: 'due', note: 'a b.md' }).toString()).toBe('status=open&group=due&note=a+b.md')
    expect(parseTaskParams(new URLSearchParams('group=nonsense&today=false')).group).toBe('project')
    expect(parseTaskParams(new URLSearchParams('today=false')).filters.today).toBeUndefined()
    expect(parseTaskParams(new URLSearchParams('status=all')).filters.status).toBeUndefined()
  })
})

describe('applyTaskFilters', () => {
  it('open is every status but done and cancelled', () => {
    expect(applyTaskFilters(tasks, { status: 'open' }, TODAY)).toHaveLength(11)
  })
  it('an exact status, priority and project each narrow the list', () => {
    expect(titles(applyTaskFilters(tasks, { status: 'blocked' }, TODAY))).toHaveLength(2)
    expect(applyTaskFilters(tasks, { priority: 'low' }, TODAY)).toHaveLength(3)
    expect(applyTaskFilters(tasks, { project: 'ipp' }, TODAY)).toHaveLength(4)
  })
  it('overdue is open tasks due before today', () => {
    expect(titles(applyTaskFilters(tasks, { overdue: true }, TODAY)).sort()).toEqual(['Confirm rate limit with SMS provider', 'Rotate staging API credentials'])
  })
  it('today is the carry-forward set: in progress, review, and planned due today or earlier', () => {
    expect(applyTaskFilters(tasks, { today: true }, TODAY)).toHaveLength(5)
    expect(isForToday(task('x', { status: 'planned', due: '2026-10-07' }), TODAY)).toBe(false)
    expect(isForToday(task('x', { status: 'planned', due: null }), TODAY)).toBe(false)
    expect(isForToday(task('x', { status: 'blocked', due: TODAY }), TODAY)).toBe(false)
  })
  it('filters combine, and ignoreStatus leaves the status out', () => {
    expect(applyTaskFilters(tasks, { status: 'blocked', project: 'ipp' }, TODAY)).toHaveLength(1)
    expect(applyTaskFilters(tasks, { status: 'blocked', project: 'ipp' }, TODAY, { ignoreStatus: true })).toHaveLength(4)
  })
})

describe('sorting and grouping', () => {
  it('sorts open before closed, then priority, then due date, no due date last', () => {
    const list = [
      task('closed high', { status: 'done', priority: 'high' }),
      task('low early', { priority: 'low', due: '2026-10-01' }),
      task('high late', { priority: 'high', due: '2026-10-20' }),
      task('high none', { priority: 'high', due: null }),
      task('high early', { priority: 'high', due: '2026-10-02' }),
      task('no priority', { priority: null, due: '2026-10-01' }),
    ]
    expect(titles([...list].sort(compareTasks))).toEqual(['high early', 'high late', 'high none', 'low early', 'no priority', 'closed high'])
  })

  const lookup = projectLookup([{ slug: 'ipp', title: 'IPP', path: 'p', status: 'active', goal: null, open_task_count: 0, modified: '' }])
  it('groups by project: by title, unknown slugs as such, no project last', () => {
    const groups = groupTasks([task('a', { project: 'ipp' }), task('b', { project: 'zzz' }), task('c'), task('d', { project: 'ipp' })], 'project', TODAY, lookup)
    expect(groups.map((g) => [g.label, g.tasks.length])).toEqual([['IPP', 2], ['zzz (unknown)', 1], ['No project', 1]])
    expect(groups[0].projectSlug).toBe('ipp')
    expect(groups[1].projectSlug).toBeUndefined()
  })
  it('groups by status in the fixed order, the seven task statuses, other statuses last', () => {
    const groups = groupTasks([...tasks, task('odd', { status: 'wip' })], 'status', TODAY, lookup)
    expect(groups.map((g) => g.label)).toEqual(['inbox', 'planned', 'in-progress', 'blocked', 'review', 'done', 'cancelled', 'Other status'])
  })
  it('groups by due: overdue, today, next 7 days, later, none, closed', () => {
    const groups = groupTasks(tasks, 'due', TODAY, lookup)
    expect(groups.map((g) => [g.label, g.tasks.length])).toEqual([
      ['Overdue', 2],
      ['Due today', 3],
      ['Next 7 days', 3],
      ['Later', 1],
      ['No due date', 2],
      ['Closed', 3],
    ])
  })
})

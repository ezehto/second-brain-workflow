import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { createMockClient } from '@/api/mock/mockClient'
import { projectFixtures, taskFixtures } from '@/api/mock/fixtures'
import type { DashboardResponse, NoteSummary } from '@/api/types'
import { projectLookup } from '@/domain/projects'
import { failed, loading, ok, renderInApp, TODAY } from '@/test/helpers'
import { task } from '@/test/notes'
import { ActiveProjects } from './ActiveProjects'
import { Integrations } from './Integrations'
import { NeedsAttention } from './NeedsAttention'
import { RecentActivity } from './RecentActivity'
import { StatTiles } from './StatTiles'
import { TasksByStatus } from './TasksByStatus'
import { TodaysFocus } from './TodaysFocus'
import { TodaysMeetings } from './TodaysMeetings'
import { TodaysStandup } from './TodaysStandup'
import { WorkflowStages } from './WorkflowStages'

const tasks = taskFixtures()
const projectList = projectFixtures()
const lookup = projectLookup(projectList)
const dashboard = (standup?: 'missing' | 'untouched' | 'touched'): Promise<DashboardResponse> =>
  createMockClient({ delayMs: 0, today: TODAY, standup }).getDashboard()

describe('StatTiles', () => {
  it('shows the five counts, each a link to its list', async () => {
    renderInApp(<StatTiles dashboard={ok(await dashboard())} tasks={ok(tasks)} />)
    const link = (label: string) => screen.getByText(label).closest('a')!
    expect(link('For today')).toHaveTextContent('5')
    expect(link('For today')).toHaveAttribute('href', '/tasks?today=true')
    expect(link('In progress')).toHaveTextContent('2')
    expect(link('Blocked')).toHaveAttribute('href', '/tasks?status=blocked')
    expect(link('Overdue')).toHaveAttribute('href', '/tasks?status=open&overdue=true')
    expect(link('In the inbox')).toHaveAttribute('href', '/inbox')
    expect(link('In the inbox')).toHaveTextContent('4')
  })
  it('counts blocked, overdue and in progress from the task list, so they match Needs attention', async () => {
    // Same tasks, a different day: the tiles follow the injected today like the attention rows do.
    renderInApp(<StatTiles dashboard={ok(await dashboard())} tasks={ok([task('a', { due: '2026-10-01' }), task('b', { status: 'blocked' })])} />)
    expect(screen.getByText('Overdue').closest('a')).toHaveTextContent('1')
    expect(screen.getByText('Blocked').closest('a')).toHaveTextContent('1')
    expect(screen.getByText('In progress').closest('a')).toHaveTextContent('0')
  })
  it('shows an error with a retry', () => {
    const q = failed<DashboardResponse>('Network down')
    renderInApp(<StatTiles dashboard={q} tasks={ok(tasks)} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Network down')
    screen.getByRole('button', { name: 'Try again' }).click()
    expect(q.refetch).toHaveBeenCalled()
  })
  it('announces loading', () => {
    renderInApp(<StatTiles dashboard={loading()} tasks={loading()} />)
    expect(screen.getByText('Loading')).toBeInTheDocument()
  })
})

describe('TodaysFocus', () => {
  it('lists the five by the stated rule, with reasons, and states the rule', () => {
    renderInApp(<TodaysFocus tasks={ok(tasks)} projects={lookup} />)
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(5)
    expect(items[0]).toHaveTextContent('Rotate staging API credentials')
    expect(items[0]).toHaveTextContent('Overdue 3 days')
    expect(items[1]).toHaveTextContent('Overdue 1 day, blocked: Waiting on the provider account manager')
    expect(within(items[0]).getByText('planned')).toBeInTheDocument()
    expect(screen.getByText(/Chosen by a fixed rule, not by an AI/)).toBeInTheDocument()
  })
  it('says so when nothing is pressing', () => {
    renderInApp(<TodaysFocus tasks={ok([task('quiet')])} projects={lookup} />)
    expect(screen.getByText('Nothing is overdue, blocked, due today or in review.')).toBeInTheDocument()
  })
  it('shows an error state', () => {
    renderInApp(<TodaysFocus tasks={failed('Boom')} projects={lookup} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Boom')
  })
  it('shows N/A for a task with no project and flags an unknown project', () => {
    const t = [task('a', { due: '2026-10-01' }), task('b', { due: '2026-10-02', project: 'ghost' })]
    renderInApp(<TodaysFocus tasks={ok(t)} projects={lookup} />)
    expect(screen.getByText('N/A')).toBeInTheDocument()
    expect(screen.getByText('ghost (unknown)')).toBeInTheDocument()
  })
})

describe('NeedsAttention', () => {
  it('shows counts and items, and N/A for incidents', () => {
    renderInApp(<NeedsAttention tasks={ok(tasks)} projects={lookup} />)
    expect(screen.getByRole('link', { name: 'Blocked' })).toHaveAttribute('href', '/tasks?status=blocked')
    expect(screen.getByText('blocked: Staging database refresh')).toBeInTheDocument()
    expect(screen.getByText('Critical incidents')).toBeInTheDocument()
    expect(screen.getByText('N/A')).toBeInTheDocument()
    expect(screen.getByText('Incidents are not tracked yet. Phase 2.')).toBeInTheDocument()
  })
  it('says what is empty in each row', () => {
    renderInApp(<NeedsAttention tasks={ok([task('quiet')])} projects={lookup} />)
    expect(screen.getByText('Nothing is blocked.')).toBeInTheDocument()
    expect(screen.getByText('Nothing is overdue.')).toBeInTheDocument()
    expect(screen.getByText('No open high-priority tasks.')).toBeInTheDocument()
    expect(screen.getByText('Nothing waiting for review.')).toBeInTheDocument()
  })
  it('shows loading and error states', () => {
    const { unmount } = renderInApp(<NeedsAttention tasks={loading<NoteSummary[]>()} projects={lookup} />)
    expect(screen.getByText('Loading')).toBeInTheDocument()
    unmount()
    renderInApp(<NeedsAttention tasks={failed('Nope')} projects={lookup} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Nope')
  })
})

describe('TasksByStatus', () => {
  it('shows the total and a legend with words and counts', () => {
    renderInApp(<TasksByStatus tasks={ok(tasks)} />)
    expect(screen.getByRole('img', { name: 'Tasks by status, 14 task notes' })).toBeInTheDocument()
    expect(screen.getByText('14 task notes')).toBeInTheDocument()
    const legend = screen.getByRole('list')
    expect(within(legend).getByText('planned').parentElement).toHaveTextContent('5')
    expect(within(legend).getByText('in-progress').parentElement).toHaveTextContent('2')
  })
  it('shows an empty state', () => {
    renderInApp(<TasksByStatus tasks={ok([])} />)
    expect(screen.getByText('No task notes in the vault yet.')).toBeInTheDocument()
  })
  it('says how many tasks have a status the donut cannot place', () => {
    renderInApp(<TasksByStatus tasks={ok([task('a'), task('b', { status: 'wip' })])} />)
    expect(screen.getByText(/1 task with a status outside the vocabulary is not counted/)).toBeInTheDocument()
  })
  it('shows an error state', () => {
    renderInApp(<TasksByStatus tasks={failed('Broken')} />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})

describe('ActiveProjects', () => {
  it('shows health by the stated rule and progress as counts', () => {
    renderInApp(<ActiveProjects projects={ok(projectList)} tasks={ok(tasks)} />)
    expect(screen.queryByText('Monitoring Dashboard')).not.toBeInTheDocument()
    const loadup = screen.getByRole('link', { name: 'LoadUp' }).closest('div')!.parentElement!
    expect(loadup).toHaveTextContent('Blocked')
    expect(loadup).toHaveTextContent('1 blocked task')
    expect(loadup).toHaveTextContent('0 of 4 done')
    const brain = screen.getByRole('link', { name: 'Second Brain' }).closest('div')!.parentElement!
    expect(brain).toHaveTextContent('On track')
    expect(brain).toHaveTextContent('1 of 3 done')
    expect(screen.getByText(/Health is a rule, not a score/)).toBeInTheDocument()
    expect(screen.getAllByRole('progressbar')).toHaveLength(3)
  })
  it('shows N/A progress and unknown health for a project with no tasks', () => {
    renderInApp(<ActiveProjects projects={ok([projectList[0]])} tasks={ok([])} />)
    expect(screen.getByText('Unknown, insufficient data')).toBeInTheDocument()
    expect(screen.getByText('N/A')).toBeInTheDocument()
  })
  it('shows an empty state when no project is active', () => {
    renderInApp(<ActiveProjects projects={ok([{ ...projectList[0], status: 'paused' }])} tasks={ok(tasks)} />)
    expect(screen.getByText('No active projects.')).toBeInTheDocument()
  })
  it('shows an error if either query fails', () => {
    renderInApp(<ActiveProjects projects={ok(projectList)} tasks={failed('Tasks failed')} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Tasks failed')
  })
})

describe('TodaysStandup', () => {
  it('says the note is not started and what would be carried forward', async () => {
    renderInApp(<TodaysStandup query={ok(await dashboard('missing'))} />)
    expect(screen.getByText('Not started')).toBeInTheDocument()
    expect(screen.getByText('Not started. 5 tasks and 2 blockers would be carried forward.')).toBeInTheDocument()
    expect(screen.getByText('01-Daily/2026/2026-10-06.md')).toBeInTheDocument()
  })
  it('distinguishes untouched from edited', async () => {
    const { unmount } = renderInApp(<TodaysStandup query={ok(await dashboard('untouched'))} />)
    expect(screen.getByText('Untouched')).toBeInTheDocument()
    unmount()
    renderInApp(<TodaysStandup query={ok(await dashboard('touched'))} />)
    expect(screen.getByText('Edited by hand')).toBeInTheDocument()
  })
})

describe('RecentActivity', () => {
  it('shows today as a time and earlier days as a date, linked to the note', async () => {
    renderInApp(<RecentActivity query={ok(await dashboard())} />)
    const first = screen.getAllByRole('listitem')[0]
    expect(first).toHaveTextContent('13:05')
    expect(first).toHaveTextContent('project, vault')
    expect(screen.getByText('Vault only until Phase 4')).toBeInTheDocument()
    expect(screen.getAllByRole('link').some((a) => a.getAttribute('href')?.startsWith('/notes?path='))).toBe(true)
  })
  it('shows an empty state', async () => {
    const d = { ...(await dashboard()), recent_activity: [] }
    renderInApp(<RecentActivity query={ok(d)} />)
    expect(screen.getByText('Nothing has changed in the vault yet.')).toBeInTheDocument()
  })
  it('shows an error state', () => {
    renderInApp(<RecentActivity query={failed('Down')} />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})

describe('preview sections', () => {
  it('labels meetings as sample data from a later phase', () => {
    renderInApp(<TodaysMeetings />)
    expect(screen.getByText('From Calendar, Phase 4. Sample data')).toBeInTheDocument()
    expect(screen.getByText('Daily standup with the team')).toBeInTheDocument()
  })
  it('labels the workflow stages as needing a stage field the plan lacks', () => {
    renderInApp(<WorkflowStages />)
    expect(screen.getByText('Needs a workflow stage on each task, not in the plan yet')).toBeInTheDocument()
    expect(screen.getByText('3 in rework.')).toBeInTheDocument()
  })
  it('shows every integration as not connected', () => {
    renderInApp(<Integrations />)
    expect(screen.getAllByText('Not connected, Phase 4')).toHaveLength(3)
  })
})

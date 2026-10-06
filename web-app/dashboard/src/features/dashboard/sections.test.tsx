import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { createMockClient } from '@/api/mock/mockClient'
import { decisionFixtures, projectFixtures, taskFixtures } from '@/api/mock/fixtures'
import type { DashboardResponse } from '@/api/types'
import { projectLookup } from '@/domain/projects'
import { failed, loading, mockClient, ok, renderApp, renderInApp, TODAY } from '@/test/helpers'
import { task } from '@/test/notes'
import { setViewport } from '@/test/viewport'
import { ActiveProjects } from './ActiveProjects'
import { BlockedWaiting } from './BlockedWaiting'
import { DecisionsToMake } from './DecisionsToMake'
import { DoneBars, DoneRecently } from './DoneRecently'
import { Focus } from './Focus'
import { Learning } from './Learning'
import { Schedule } from './Schedule'
import { StandupPanel } from './StandupPanel'
import { StatTiles } from './StatTiles'
import { TasksByStatus } from './TasksByStatus'
import { WorkflowStrip } from './WorkflowStrip'

const tasks = taskFixtures()
const decisions = decisionFixtures()
const projectList = projectFixtures()
const lookup = projectLookup(projectList)
const dashboard = (standup?: 'missing' | 'untouched' | 'touched'): Promise<DashboardResponse> =>
  createMockClient({ delayMs: 0, today: TODAY, standup }).getDashboard()

describe('StatTiles', () => {
  it('shows six counts, each a link to its list', async () => {
    renderInApp(<StatTiles dashboard={ok(await dashboard())} tasks={ok(tasks)} decisions={ok(decisions)} project={null} />)
    const link = (label: string) => screen.getByText(label).closest('a')!
    expect(link('For today')).toHaveTextContent('5')
    expect(link('For today')).toHaveAttribute('href', '/tasks?today=true')
    expect(link('In progress')).toHaveTextContent('2')
    expect(link('Blocked')).toHaveAttribute('href', '/tasks?status=blocked')
    expect(link('Overdue')).toHaveTextContent('2')
    expect(link('Overdue')).toHaveAttribute('href', '/tasks?status=open&overdue=true')
    expect(link('In the inbox')).toHaveTextContent('4')
    expect(link('In the inbox')).toHaveAttribute('href', '/inbox')
    expect(link('Decisions pending')).toHaveTextContent('1')
    expect(link('Decisions pending')).toHaveAttribute('href', '/decisions?status=proposed')
    expect(link('Blocked')).toHaveClass('h-16')
  })
  it('carries the project context in its links and counts only that project', async () => {
    const ipp = tasks.filter((t) => t.project === 'ipp')
    renderInApp(<StatTiles dashboard={ok(await dashboard())} tasks={ok(ipp)} decisions={ok(decisions.filter((d) => d.project === 'ipp'))} project="ipp" />)
    expect(screen.getByText('Blocked').closest('a')).toHaveAttribute('href', '/tasks?status=blocked&project=ipp')
    expect(screen.getByText('Blocked').closest('a')).toHaveTextContent('1')
    expect(screen.getByText('For today').closest('a')).toHaveTextContent('2')
    expect(screen.getByText('Decisions pending').closest('a')).toHaveTextContent('1')
  })
  it('counts from the task list, so it follows the injected today', async () => {
    renderInApp(<StatTiles dashboard={ok(await dashboard())} tasks={ok([task('a', { due: '2026-10-01' }), task('b', { status: 'blocked' })])} decisions={ok([])} project={null} />)
    expect(screen.getByText('Overdue').closest('a')).toHaveTextContent('1')
    expect(screen.getByText('Blocked').closest('a')).toHaveTextContent('1')
    expect(screen.getByText('Decisions pending').closest('a')).toHaveTextContent('0')
  })
  it('shows an error with a retry, and announces loading', () => {
    const q = failed<DashboardResponse>('Network down')
    const { unmount } = renderInApp(<StatTiles dashboard={q} tasks={ok(tasks)} decisions={ok(decisions)} project={null} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Network down')
    screen.getByRole('button', { name: 'Try again' }).click()
    expect(q.refetch).toHaveBeenCalled()
    unmount()
    renderInApp(<StatTiles dashboard={loading()} tasks={loading()} decisions={loading()} project={null} />)
    expect(screen.getByText('Loading')).toBeInTheDocument()
  })
})

describe('Focus', () => {
  it('lists the five by the stated rule as task rows with a status control, and marks only the first Next', () => {
    renderInApp(<Focus tasks={ok(tasks)} projects={lookup} project={null} />)
    const rows = screen.getAllByRole('link').filter((a) => a.getAttribute('href')?.startsWith('/notes?path='))
    expect(rows).toHaveLength(5)
    expect(rows[0]).toHaveTextContent('Rotate staging API credentials')
    expect(screen.getAllByText(/Next\./)).toHaveLength(1)
    expect(screen.getByText(/Overdue 3 days/)).toBeInTheDocument()
    expect(screen.getByText(/Overdue 1 day, blocked: Waiting on the provider account manager/)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Change status of/ })).toHaveLength(5)
    expect(screen.getByRole('heading', { name: 'Focus' })).toBeInTheDocument()
  })
  it('has the rule in a tooltip trigger, named for assistive technology, and no accent fill', () => {
    const { container } = renderInApp(<Focus tasks={ok(tasks)} projects={lookup} project={null} />)
    expect(screen.getByRole('button', { name: /How focus is chosen: Chosen by a fixed rule, not by an AI/ })).toBeInTheDocument()
    expect(container.querySelector('[data-accent]')).toBeNull()
  })
  it('says so when nothing is pressing', () => {
    renderInApp(<Focus tasks={ok([task('quiet')])} projects={lookup} project={null} />)
    expect(screen.getByText('Nothing is overdue, blocked, due today or in review.')).toBeInTheDocument()
  })
  it('shows N/A for a task with no project and flags an unknown project', () => {
    renderInApp(<Focus tasks={ok([task('a', { due: '2026-10-01' }), task('b', { due: '2026-10-02', project: 'ghost' })])} projects={lookup} project={null} />)
    expect(screen.getByText(/· N\/A/)).toBeInTheDocument()
    expect(screen.getByText(/· ghost \(unknown\)/)).toBeInTheDocument()
  })
  it('shows loading and error states', () => {
    const { unmount } = renderInApp(<Focus tasks={loading()} projects={lookup} project={null} />)
    expect(screen.getByText('Loading')).toBeInTheDocument()
    unmount()
    renderInApp(<Focus tasks={failed('Boom')} projects={lookup} project={null} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Boom')
  })
})

describe('BlockedWaiting', () => {
  it('shows each blocked task with what it waits on and its age, without repeating a Blocked marker', () => {
    renderInApp(<BlockedWaiting tasks={ok(tasks)} projects={lookup} />)
    expect(screen.getByRole('heading', { name: 'Blocked and waiting' })).toBeInTheDocument()
    expect(screen.getByText('Waiting on the provider account manager · LoadUp')).toBeInTheDocument()
    expect(screen.getByText('Staging database refresh · IPP')).toBeInTheDocument()
    expect(screen.getAllByText('1 day')).toHaveLength(2)
    expect(screen.queryByText(/^Blocked:/)).not.toBeInTheDocument()
  })
  it('says when nothing is blocked, and shows an error state', () => {
    const { unmount } = renderInApp(<BlockedWaiting tasks={ok([task('quiet')])} projects={lookup} />)
    expect(screen.getByText('Nothing is blocked.')).toBeInTheDocument()
    unmount()
    renderInApp(<BlockedWaiting tasks={failed('Nope')} projects={lookup} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Nope')
  })
  it('shows N/A for a blocker that was never written down', () => {
    renderInApp(<BlockedWaiting tasks={ok([task('stuck', { status: 'blocked' })])} projects={lookup} />)
    expect(screen.getByText('N/A · N/A')).toBeInTheDocument()
  })
})

describe('DecisionsToMake', () => {
  it('lists proposed decisions only, opening the note reader, with project and age', () => {
    renderInApp(<DecisionsToMake decisions={ok(decisions)} projects={lookup} />)
    const link = screen.getByRole('link', { name: 'Use idempotency keys on payment callbacks' })
    expect(link).toHaveAttribute('href', '/notes?path=05-Knowledge%2FDecisions%2FUse%20idempotency%20keys%20on%20payment%20callbacks.md')
    expect(screen.getByText('IPP · proposed 1 day ago')).toBeInTheDocument()
    expect(screen.queryByText('Poll the vault instead of file watching')).not.toBeInTheDocument()
  })
  it('has empty, loading and error states', () => {
    const a = renderInApp(<DecisionsToMake decisions={ok([])} projects={lookup} />)
    expect(screen.getByText('No decision is waiting.')).toBeInTheDocument()
    a.unmount()
    const b = renderInApp(<DecisionsToMake decisions={loading()} projects={lookup} />)
    expect(screen.getByText('Loading')).toBeInTheDocument()
    b.unmount()
    renderInApp(<DecisionsToMake decisions={failed('Down')} projects={lookup} />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})

describe('DoneRecently', () => {
  it('shows tasks done in the last 7 days with their evidence line, labelled approximate', async () => {
    renderInApp(<DoneRecently tasks={ok(tasks)} />, mockClient())
    expect(screen.getByRole('heading', { name: 'Done recently' })).toBeInTheDocument()
    expect(screen.getByText('Approximate, by last change')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Reproduce duplicate settlement rows' })).toBeInTheDocument()
    expect(await screen.findByText('Reproduced on staging: a retried callback wrote the row twice.')).toBeInTheDocument()
    expect(await screen.findByText('No evidence recorded.')).toBeInTheDocument()
  })
  it('leaves out tasks done before the window and tasks not done', () => {
    const old = task('Ancient', { status: 'done', modified: '2026-09-01T10:00:00+08:00' })
    renderInApp(<DoneRecently tasks={ok([old, task('Open')])} />)
    expect(screen.getByText('Nothing finished in the last 7 days.')).toBeInTheDocument()
  })
  it('draws done per day with the numbers as text', () => {
    renderInApp(<DoneBars days={[{ date: '2026-10-05', count: 3 }, { date: '2026-10-06', count: 0 }]} />)
    const bars = screen.getByRole('list', { name: /Tasks done per day: Oct 5 3, Oct 6 0/ })
    expect(within(bars).getByText('3')).toBeInTheDocument()
    expect(screen.getByText(/3 in 7 days, approximate/)).toBeInTheDocument()
  })
  it('shows an error state', () => {
    renderInApp(<DoneRecently tasks={failed('Bad')} />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})

describe('ActiveProjects', () => {
  it('shows health with its reason, the blocked or next item, and progress as counts', () => {
    renderInApp(<ActiveProjects projects={ok(projectList)} tasks={ok(tasks)} project={null} />)
    expect(screen.queryByText('Monitoring Dashboard')).not.toBeInTheDocument()
    const row = (name: string) => screen.getByRole('link', { name }).closest('div[class*="min-h"]') as HTMLElement
    expect(row('LoadUp')).toHaveTextContent('Blocked')
    expect(row('LoadUp')).toHaveTextContent('1 blocked task')
    expect(row('LoadUp')).toHaveTextContent('Blocked: Confirm rate limit with SMS provider')
    expect(row('LoadUp')).toHaveTextContent('0 of 4 done')
    expect(row('Second Brain')).toHaveTextContent('On track')
    expect(row('Second Brain')).toHaveTextContent('Next: Verify templates in Obsidian')
    expect(row('Second Brain')).toHaveTextContent('1 of 3 done')
    expect(screen.getAllByRole('progressbar')).toHaveLength(3)
    expect(screen.getByRole('link', { name: 'LoadUp' })).toHaveAttribute('href', '/projects/loadup')
    expect(screen.getByRole('button', { name: /How project health is decided/ })).toBeInTheDocument()
  })
  it('narrows to the project context', () => {
    renderInApp(<ActiveProjects projects={ok(projectList)} tasks={ok(tasks)} project="ipp" />)
    expect(screen.getByRole('link', { name: 'IPP' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'LoadUp' })).not.toBeInTheDocument()
  })
  it('shows N/A progress and unknown health for a project with no tasks, and says so when none is active', () => {
    const a = renderInApp(<ActiveProjects projects={ok([projectList[0]])} tasks={ok([])} project={null} />)
    expect(screen.getByText('Unknown, insufficient data')).toBeInTheDocument()
    expect(screen.getByText('N/A')).toBeInTheDocument()
    expect(screen.getByText('No open tasks.')).toBeInTheDocument()
    a.unmount()
    renderInApp(<ActiveProjects projects={ok([{ ...projectList[0], status: 'paused' }])} tasks={ok(tasks)} project={null} />)
    expect(screen.getByText('No active projects.')).toBeInTheDocument()
  })
  it('shows an error if either query fails', () => {
    renderInApp(<ActiveProjects projects={ok(projectList)} tasks={failed('Tasks failed')} project={null} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Tasks failed')
  })
})

describe('TasksByStatus', () => {
  it('shows a 120px donut, the total, and a legend with words and counts', () => {
    renderInApp(<TasksByStatus tasks={ok(tasks)} />)
    const chart = screen.getByRole('img', { name: 'Tasks by status, 14 task notes' })
    expect(chart).toHaveStyle({ width: '120px', height: '120px' })
    expect(screen.getByRole('heading', { name: 'Where do my tasks stand?' })).toBeInTheDocument()
    const legend = screen.getByRole('list')
    expect(within(legend).getByText('planned').parentElement).toHaveTextContent('5')
    expect(within(legend).getByText('in-progress').parentElement).toHaveTextContent('2')
  })
  it('has empty, unknown-status and error states', () => {
    const a = renderInApp(<TasksByStatus tasks={ok([])} />)
    expect(screen.getByText('No task notes yet.')).toBeInTheDocument()
    a.unmount()
    const b = renderInApp(<TasksByStatus tasks={ok([task('a'), task('b', { status: 'wip' })])} />)
    expect(screen.getByText(/1 task with a status outside the vocabulary is not counted/)).toBeInTheDocument()
    b.unmount()
    renderInApp(<TasksByStatus tasks={failed('Broken')} />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})

describe('StandupPanel', () => {
  const panel = async (standup: 'missing' | 'untouched' | 'touched') => {
    const client = mockClient({ standup })
    renderInApp(<StandupPanel dashboard={ok(await client.getDashboard())} projects={ok(projectList)} tasks={ok(tasks)} />, client)
    return client
  }
  it('offers Start standup, with what would be carried forward, when the note is missing', async () => {
    await panel('missing')
    expect(screen.getByText('Not started')).toBeInTheDocument()
    expect(screen.getByText('Not started. 5 tasks and 2 blockers would be carried forward.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start standup' })).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })
  it('offers Fill with carry-forward when untouched, and an add field per section', async () => {
    await panel('untouched')
    expect(screen.getByRole('button', { name: 'Fill with carry-forward' })).toBeInTheDocument()
    for (const s of ['Done', 'Today', 'Blockers']) expect(screen.getByRole('textbox', { name: `Add a line to ${s}` })).toBeInTheDocument()
  })
  it('shows the sections as written when edited by hand, with an add field each', async () => {
    await panel('touched')
    expect(screen.getByText('Edited by hand')).toBeInTheDocument()
    expect(screen.getByText('Pair with QA on the OTP reproduction')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Start standup|Fill with carry-forward/ })).not.toBeInTheDocument()
    expect(screen.getAllByRole('textbox')).toHaveLength(3)
  })
  it('has loading and error states', () => {
    const a = renderInApp(<StandupPanel dashboard={loading()} projects={loading()} tasks={loading()} />)
    expect(screen.getByText('Loading')).toBeInTheDocument()
    a.unmount()
    renderInApp(<StandupPanel dashboard={failed('Gone')} projects={loading()} tasks={loading()} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Gone')
  })
})

describe('preview panels', () => {
  it('Schedule and Learning carry one Preview badge each with the source in its name', () => {
    const a = renderInApp(<Schedule />)
    expect(screen.getByRole('button', { name: /Preview: From Calendar, Phase 4. Sample data/ })).toBeInTheDocument()
    expect(screen.getByText('Daily standup with the team')).toBeInTheDocument()
    a.unmount()
    renderInApp(<Learning />)
    expect(screen.getByRole('button', { name: /Preview: From the upskilling notes, Phase 3/ })).toBeInTheDocument()
    expect(screen.getByText(/Idempotency and retries/)).toBeInTheDocument()
  })
  it('WorkflowStrip shows six figures, the rework line and the badge', () => {
    renderInApp(<WorkflowStrip />)
    expect(screen.getAllByRole('listitem')).toHaveLength(6)
    expect(screen.getByText('3 in rework.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Preview: Needs a workflow stage/ })).toBeInTheDocument()
  })
})

describe('Dashboard page', () => {
  it('uses three columns at 1920 and keeps Focus, Blocked and Standup at the top of each', async () => {
    setViewport(1920)
    renderApp()
    const focus = await screen.findByRole('region', { name: 'Focus' })
    const columns = focus.parentElement!.parentElement!.children
    expect(columns).toHaveLength(3)
    expect(within(columns[0] as HTMLElement).getByRole('region', { name: 'Active projects' })).toBeInTheDocument()
    expect(within(columns[1] as HTMLElement).getByRole('region', { name: 'Blocked and waiting' })).toBeInTheDocument()
    expect(within(columns[1] as HTMLElement).getByRole('region', { name: 'Done recently' })).toBeInTheDocument()
    expect(within(columns[2] as HTMLElement).getByRole('region', { name: 'Standup today' })).toBeInTheDocument()
  })
  it('uses two columns at 1440 and one on a phone, in the phone order', async () => {
    const view = renderApp()
    const focus = await screen.findByRole('region', { name: 'Focus' })
    expect(focus.parentElement!.parentElement!.children).toHaveLength(2)
    view.unmount()
    setViewport(390)
    renderApp()
    const first = await screen.findByRole('region', { name: 'Focus' })
    const column = first.parentElement!
    expect(column.parentElement!.children).toHaveLength(1)
    expect([...column.children].map((c) => c.getAttribute('aria-label'))).toEqual([
      'Focus',
      'Blocked and waiting',
      'Decisions to make',
      'Standup today',
      'Active projects',
      'Done recently',
      'Tasks by status',
      'Schedule',
      'Learning',
    ])
  })
  it('has no Needs attention, Claude usage or Integrations', async () => {
    renderApp()
    await screen.findByRole('region', { name: 'Focus' })
    for (const gone of ['Needs attention', 'Integrations', 'Claude usage', 'How you are improving']) expect(screen.queryByText(gone)).not.toBeInTheDocument()
  })
  it('follows the project context in every panel', async () => {
    renderApp('/?project=ipp')
    const focus = await screen.findByRole('region', { name: 'Focus' })
    await waitFor(() => expect(within(focus).getAllByRole('link', { name: /Load test wallet|Add retry|Confirm rate|Rotate|Investigate|Fix N/ }).length).toBeGreaterThan(0))
    expect(within(focus).queryByRole('link', { name: 'Rotate staging API credentials' })).not.toBeInTheDocument()
    expect(within(focus).getByRole('link', { name: 'Load test wallet reservation path' })).toBeInTheDocument()
    const blocked = screen.getByRole('region', { name: 'Blocked and waiting' })
    expect(within(blocked).queryByRole('link', { name: 'Confirm rate limit with SMS provider' })).not.toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Active projects' })).queryByRole('link', { name: 'LoadUp' })).not.toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Decisions to make' })).getByText(/IPP · proposed/)).toBeInTheDocument()
  })
  it('starts the standup in place, then shows the sections with add fields', async () => {
    const user = userEvent.setup()
    renderApp()
    await user.click(await screen.findByRole('button', { name: 'Start standup' }))
    expect(await screen.findByRole('textbox', { name: 'Add a line to Today' })).toBeInTheDocument()
    expect(await screen.findByText('Edited by hand')).toBeInTheDocument()
  })
  it('adds a line to a section through the append endpoint and shows it', async () => {
    const user = userEvent.setup()
    renderApp('/', mockClient({ standup: 'touched' }))
    const field = await screen.findByRole('textbox', { name: 'Add a line to Blockers' })
    await user.type(field, 'Waiting on infra')
    await user.click(within(field.closest('section')!).getByRole('button', { name: 'Add' }))
    expect(await screen.findByText('Waiting on infra')).toBeInTheDocument()
  })
  it('fills an untouched standup with carry-forward before adding a line, like the Fill button', async () => {
    const user = userEvent.setup()
    const client = mockClient({ standup: 'untouched' })
    renderApp('/', client)
    const field = await screen.findByRole('textbox', { name: 'Add a line to Today' })
    await user.type(field, 'Reply to QA')
    await user.click(within(field.closest('section')!).getByRole('button', { name: 'Add' }))
    await waitFor(async () => {
      const standup = await client.getStandupToday()
      expect(standup.exists && standup.note.body).toContain('Reply to QA')
      expect(standup.exists && standup.note.body).toContain('[[Investigate missing OTP email]]')
    })
    expect(screen.queryByRole('button', { name: 'Fill with carry-forward' })).not.toBeInTheDocument()
  })
  it('changes a Focus task status in place', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    renderApp('/', client)
    const focus = await screen.findByRole('region', { name: 'Focus' })
    await user.click(await within(focus).findByRole('button', { name: /Status: planned\. Change status of Rotate staging/ }))
    await user.click(await screen.findByRole('menuitemradio', { name: 'in-progress' }))
    await waitFor(async () => expect((await client.lookupNote({ path: '02-Work/Tasks/Rotate staging API credentials.md' })).status).toBe('in-progress'))
  })
})

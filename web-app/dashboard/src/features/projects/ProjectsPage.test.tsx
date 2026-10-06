import { configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ApiError } from '@/api/client'
import { NotePage } from '@/features/notes/NotePage'
import { renderRoutes } from '@/features/notes/testing'
import { mockClient } from '@/test/helpers'
import { ProjectPage } from './ProjectPage'
import { ProjectsPage } from './ProjectsPage'

configure({ asyncUtilTimeout: 5000 })

const routes = [
  { path: '/projects', element: <ProjectsPage /> },
  { path: '/projects/:slug', element: <ProjectPage /> },
  { path: '/notes', element: <NotePage /> },
]
const open = (url = '/projects', client = mockClient(), width = 1440) => renderRoutes(routes, url, client, width)
const bodyRows = () => within(screen.getAllByRole('rowgroup')[1]).getAllByRole('row')

describe('ProjectsPage', () => {
  it('shows loading, then a row per project with status and open count', async () => {
    open()
    expect(screen.getByText('Loading')).toBeInTheDocument()
    await screen.findByRole('link', { name: 'IPP' })
    const ipp = within(screen.getByRole('link', { name: 'IPP' }).closest('tr') as HTMLElement)
    expect(ipp.getByText('active')).toBeInTheDocument()
    expect(ipp.getAllByRole('cell')[2]).toHaveTextContent('3') // open
    expect(ipp.getByText('Blocked')).toBeInTheDocument()
    expect(ipp.getByText('1 blocked task')).toBeInTheDocument()
    expect(ipp.getByRole('link', { name: /Add retry|Load test|Write runbook/ })).toBeInTheDocument()
  })

  it('sorts by health severity, then name', async () => {
    open()
    await screen.findByRole('link', { name: 'IPP' })
    const names = bodyRows().map((r) => within(r).getAllByRole('rowheader')[0].textContent)
    expect(names).toEqual(['IPP', 'LoadUp', 'Monitoring Dashboard', 'Second Brain'])
  })

  it('links the name to the project view', async () => {
    open()
    expect(await screen.findByRole('link', { name: 'IPP' })).toHaveAttribute('href', '/projects/ipp')
  })

  it('marks the row named by the project context parameter', async () => {
    open('/projects?project=loadup')
    await screen.findByRole('link', { name: 'IPP' })
    const current = bodyRows().filter((r) => r.getAttribute('aria-current') === 'true')
    expect(current).toHaveLength(1)
    expect(within(current[0]).getByRole('link', { name: 'LoadUp' })).toBeInTheDocument()
  })

  it('states the health rule behind a control, not a footnote', async () => {
    open()
    await screen.findByRole('link', { name: 'IPP' })
    expect(screen.getByRole('button', { name: /How health is decided/ })).toHaveAccessibleName(/At risk: at least one overdue open task/)
  })

  it('becomes two-line rows on a phone', async () => {
    open('/projects', mockClient(), 390)
    await screen.findByRole('link', { name: 'IPP' })
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByText(/3 open, 1 blocked, 0 overdue/)).toBeInTheDocument()
  })

  it('says what to do when there are no projects', async () => {
    const client = mockClient()
    client.listProjects = async () => []
    open('/projects', client)
    expect(await screen.findByText(/No project notes yet/)).toBeInTheDocument()
  })

  it('shows an error with a retry', async () => {
    const client = mockClient()
    let calls = 0
    const real = client.listProjects
    client.listProjects = async () => {
      if (calls++ === 0) throw new Error('boom')
      return real()
    }
    open('/projects', client)
    expect(await screen.findByText(/boom/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(await screen.findByRole('link', { name: 'IPP' })).toBeInTheDocument()
  })
})

describe('ProjectPage', () => {
  it('shows the header, the four counts and the one progress bar', async () => {
    open('/projects/ipp')
    expect(await screen.findByRole('heading', { name: 'IPP' })).toBeInTheDocument()
    expect(screen.getAllByText('Blocked').length).toBeGreaterThan(0)
    expect(screen.getByText('1 blocked task')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Open/ })).toHaveAttribute('href', '/tasks?status=open&project=ipp')
    expect(screen.getByRole('link', { name: /1 of 4/ })).toBeInTheDocument()
    expect(screen.getAllByRole('progressbar')).toHaveLength(1)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '25')
  })

  it('renders every Overview section', async () => {
    open('/projects/ipp')
    await screen.findByRole('heading', { name: 'IPP' })
    for (const title of ['What is blocked, and on what?', 'Next tasks', 'Proposed decisions', 'Recent notes', 'How many tasks are in each status?', 'What is due soon?']) {
      expect(await screen.findByRole('heading', { name: new RegExp(title) })).toBeInTheDocument()
    }
    const blockers = screen.getByRole('heading', { name: /What is blocked/ }).closest('section') as HTMLElement
    expect(within(blockers).getByText('Load test wallet reservation path')).toBeInTheDocument()
    expect(within(blockers).getByText(/Blocked: Staging database refresh/)).toBeInTheDocument()
    const decisions = screen.getByRole('heading', { name: 'Proposed decisions' }).closest('section') as HTMLElement
    expect(within(decisions).getByText('Use idempotency keys on payment callbacks')).toBeInTheDocument()
    expect(within(decisions).queryByText('Settlement reruns by full file replace')).not.toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Project tasks by status, 4 task notes/ })).toBeInTheDocument()
    expect(screen.getByText('Settlement rerun runbook due')).toBeInTheDocument()
  })

  it('shows a not-found state with a way back for an unknown slug', async () => {
    open('/projects/nope')
    expect(await screen.findByRole('heading', { name: 'Project not found' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to all projects' })).toHaveAttribute('href', '/projects')
  })

  it('shows other errors with a retry rather than not found', async () => {
    const client = mockClient()
    client.getProject = async () => {
      throw new ApiError(500, 'server fell over')
    }
    open('/projects/ipp', client)
    expect(await screen.findByText(/server fell over/)).toBeInTheDocument()
    expect(screen.queryByText('Project not found')).not.toBeInTheDocument()
  })

  it('switches tabs through the tab parameter', async () => {
    const { router } = open('/projects/ipp')
    await screen.findByRole('heading', { name: 'IPP' })
    await userEvent.click(screen.getByRole('button', { name: 'Decisions' }))
    expect(router.state.location.search).toBe('?tab=decisions')
    expect(await screen.findByRole('heading', { name: 'Decisions' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Overview' }))
    expect(router.state.location.search).toBe('')
  })

  it('opens the tab named in the URL and falls back to Overview for an unknown one', async () => {
    open('/projects/ipp?tab=tasks')
    expect(await screen.findByRole('heading', { name: 'Tasks' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Tasks' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('falls back to Overview for an unknown tab', async () => {
    open('/projects/ipp?tab=bogus')
    expect(await screen.findByRole('heading', { name: 'Next tasks' })).toBeInTheDocument()
  })

  it('groups the project tasks by status on the Tasks tab', async () => {
    open('/projects/ipp?tab=tasks')
    await screen.findByRole('heading', { name: 'Tasks' })
    const groups = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
    expect(groups).toEqual(['planned', 'in-progress', 'blocked', 'done'])
  })

  it('opens the reader on a task row and closes it', async () => {
    const { router } = open('/projects/ipp?tab=tasks')
    await userEvent.click(await screen.findByRole('link', { name: 'Load test wallet reservation path' }))
    expect(new URLSearchParams(router.state.location.search).get('note')).toBe('02-Work/Tasks/Load test wallet reservation path.md')
    const pane = await screen.findByRole('complementary', { name: 'Open note' })
    expect(await within(pane).findByRole('heading', { name: 'Load test wallet reservation path' })).toBeInTheDocument()
    await userEvent.click(within(pane).getByRole('button', { name: 'Close note' }))
    await waitFor(() => expect(screen.queryByRole('complementary')).not.toBeInTheDocument())
  })

  it('opens the reader on a decision row, proposed first', async () => {
    open('/projects/ipp?tab=decisions')
    await screen.findByRole('heading', { name: 'Decisions' })
    const titles = screen.getAllByRole('listitem').map((li) => within(li).getAllByRole('link')[0].textContent)
    expect(titles).toEqual(['Use idempotency keys on payment callbacks', 'Settlement reruns by full file replace'])
    await userEvent.click(screen.getByRole('link', { name: titles[0]! }))
    expect(await screen.findByRole('complementary', { name: 'Open note' })).toBeInTheDocument()
  })

  it('lists lessons and other notes on the Notes tab and opens the reader', async () => {
    open('/projects/ipp?tab=notes')
    await userEvent.click(await screen.findByRole('link', { name: 'A retry on a business rejection duplicates the send' }))
    expect(await screen.findByRole('complementary', { name: 'Open note' })).toBeInTheDocument()
  })

  it('does not use a pane below the split width: the title links to the note route', async () => {
    open('/projects/ipp?tab=tasks', mockClient(), 800)
    const link = await screen.findByRole('link', { name: 'Load test wallet reservation path' })
    expect(link).toHaveAttribute('href', expect.stringContaining('/notes?path='))
    await userEvent.click(link)
    expect(await screen.findByRole('article')).toBeInTheDocument()
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
  })

  it('shows empty states for a project with no tasks', async () => {
    const client = mockClient()
    const real = client.listNotes
    client.listNotes = async (p) => (p?.type === 'task' && p.project === 'monitoring-dashboard' ? { count: 0, next: null, previous: null, results: [] } : real(p))
    open('/projects/monitoring-dashboard', client)
    expect(await screen.findByText('Nothing is blocked.')).toBeInTheDocument()
    expect(screen.getByText('No open tasks. Use New in the header to add one.')).toBeInTheDocument()
    expect(screen.getByText('No tasks to count.')).toBeInTheDocument()
    expect(screen.getByText('No milestones for this project yet.')).toBeInTheDocument()
  })
})

describe('ProjectPage Later tabs', () => {
  it.each([
    ['timeline', /What happened in this project/],
    ['architecture', /How does a payment callback flow/],
    ['incidents', /What went wrong here/],
    ['deployments', /What was deployed/],
    ['learning', /What did this project teach/],
  ])('%s shows one preview badge and its content', async (tab, heading) => {
    open(`/projects/ipp?tab=${tab}`)
    expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /^Preview/ })).toHaveLength(1)
  })

  it('timeline lists the project events with their source', async () => {
    open('/projects/ipp?tab=timeline')
    expect(await screen.findByText('Add retry with backoff to payment callback handler')).toBeInTheDocument()
    expect(screen.getAllByText('GitLab').length).toBeGreaterThan(0)
    expect(screen.queryByText(/OTP emails: relay log sample/)).not.toBeInTheDocument()
  })

  it('architecture shows a detail panel that follows the selected node', async () => {
    open('/projects/ipp?tab=architecture')
    expect(await screen.findByRole('heading', { name: 'Callback handler', level: 3 })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Bank SFTP/ }))
    expect(screen.getByRole('heading', { name: 'Bank SFTP', level: 3 })).toBeInTheDocument()
    expect(screen.getByText(/financial error/)).toBeInTheDocument()
  })

  it('is empty, not broken, for a project with no sample data', async () => {
    open('/projects/loadup?tab=architecture')
    expect(await screen.findByText('No architecture sample for this project.')).toBeInTheDocument()
  })
})

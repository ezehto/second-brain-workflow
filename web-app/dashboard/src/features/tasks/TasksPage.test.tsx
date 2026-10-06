import { configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/api/client'
import { NotePage } from '@/features/notes/NotePage'
import { renderRoutes } from '@/features/notes/testing'
import { mockClient } from '@/test/helpers'
import { TasksPage } from './TasksPage'

// The suite shares a slow WSL mount with other work; findBy's default 1s is too tight there.
configure({ asyncUtilTimeout: 5000 })

const routes = [
  { path: '/tasks', element: <TasksPage /> },
  { path: '/notes', element: <NotePage /> },
]
const open = (url: string, client = mockClient(), width = 1440) => renderRoutes(routes, url, client, width)
const search = (router: { state: { location: { search: string } } }) => new URLSearchParams(router.state.location.search)
const ROTATE = 'Rotate staging API credentials'

const groupHeadings = () => screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
const rowTitles = () => screen.getAllByRole('listitem').map((li) => within(li).getAllByRole('link')[0].textContent)

describe('TasksPage: what the URL filters', () => {
  it('shows every task with no filter, in the loading then loaded states', async () => {
    open('/tasks')
    expect(screen.getByText('Loading')).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: ROTATE })).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(14)
  })

  it.each([
    ['status=blocked', 2],
    ['status=open&overdue=true', 2],
    ['overdue=true', 2],
    ['today=true', 5],
    ['status=open', 11],
    ['priority=low', 3],
    ['project=ipp', 4],
    ['status=review&project=loadup&priority=medium', 1],
  ])('/tasks?%s lists %i tasks', async (query, count) => {
    open(`/tasks?${query}`)
    await screen.findAllByRole('listitem')
    expect(screen.getAllByRole('listitem')).toHaveLength(count)
  })

  it('shows the count in the heading and says so when nothing matches, with a way out', async () => {
    open('/tasks?status=blocked&priority=low')
    expect(await screen.findByText('No tasks match these filters.')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Clear filters' }).at(-1)).toHaveAttribute('href', '/tasks')
  })

  it('says what to do when the vault has no tasks', async () => {
    const client = mockClient()
    client.listNotes = async () => ({ count: 0, next: null, previous: null, results: [] })
    open('/tasks', client)
    expect(await screen.findByText(/No task notes yet/)).toBeInTheDocument()
  })

  it('shows an error with a retry that asks again', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    const real = client.listNotes
    let fail = true
    client.listNotes = async (p) => {
      if (fail) throw new Error('Network down')
      return real(p)
    }
    open('/tasks', client)
    expect(await screen.findByRole('alert')).toHaveTextContent('Network down')
    fail = false
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('link', { name: ROTATE })).toBeInTheDocument()
  })
})

describe('TasksPage: controls write the URL', () => {
  it('the project and priority selects, and the overdue and today checkboxes, set their parameters', async () => {
    const user = userEvent.setup()
    const { router } = open('/tasks')
    await screen.findAllByRole('listitem')
    await user.selectOptions(screen.getByLabelText('Project'), 'ipp')
    await user.selectOptions(screen.getByLabelText('Priority'), 'high')
    await user.click(screen.getByLabelText('Overdue only'))
    await user.click(screen.getByLabelText('For today'))
    expect(search(router).toString()).toBe('priority=high&project=ipp&today=true&overdue=true')
    await user.selectOptions(screen.getByLabelText('Project'), '')
    await user.click(screen.getByLabelText('Overdue only'))
    expect(search(router).toString()).toBe('priority=high&today=true')
  })

  it('the status bar filters: a status, Open, and All', async () => {
    const user = userEvent.setup()
    const { router } = open('/tasks')
    await screen.findAllByRole('listitem')
    await user.click(screen.getByRole('button', { name: /^blocked 2$/ }))
    expect(search(router).get('status')).toBe('blocked')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByRole('button', { name: /^blocked 2$/ })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: /^Open 11$/ }))
    expect(search(router).get('status')).toBe('open')
    await user.click(screen.getByRole('button', { name: /^All 14$/ }))
    expect(search(router).has('status')).toBe(false)
    expect(screen.getAllByRole('listitem')).toHaveLength(14)
  })

  it('the bar shows each status count as text, following the other filters but not the status', async () => {
    open('/tasks?project=ipp&status=done')
    await screen.findAllByRole('listitem')
    const bar = screen.getByRole('group', { name: 'Filter by status' })
    expect(within(bar).getByRole('button', { name: /^done 1$/ })).toBeInTheDocument()
    expect(within(bar).getByRole('button', { name: /^in-progress 1$/ })).toBeInTheDocument()
    expect(within(bar).getByRole('button', { name: /^cancelled 0$/ })).toBeInTheDocument()
    expect(within(bar).getByRole('button', { name: /^All 4$/ })).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
  })

  it('group by is written to the URL', async () => {
    const user = userEvent.setup()
    const { router } = open('/tasks')
    await screen.findAllByRole('listitem')
    await user.click(screen.getByRole('button', { name: 'Due' }))
    expect(search(router).get('group')).toBe('due')
    await user.click(screen.getByRole('button', { name: 'Project' }))
    expect(search(router).has('group')).toBe(false)
  })

  it('a project in the URL that names no project note stays visible as unknown', async () => {
    open('/tasks?project=loadup-v2')
    expect(await screen.findByRole('option', { name: 'loadup-v2 (unknown)' })).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
  })
})

describe('TasksPage: groups and order', () => {
  it('groups by status into the seven task statuses', async () => {
    open('/tasks?group=status')
    await screen.findAllByRole('listitem')
    expect(groupHeadings()).toEqual(['inbox', 'planned', 'in-progress', 'blocked', 'review', 'done', 'cancelled'])
  })

  it('groups by project by default, with the project as a link, and sorts by priority then due', async () => {
    open('/tasks?project=loadup&status=open')
    await screen.findAllByRole('listitem')
    expect(screen.getByRole('heading', { level: 3, name: 'LoadUp' }).querySelector('a')).toHaveAttribute('href', '/projects/loadup')
    expect(rowTitles()).toEqual([ROTATE, 'Confirm rate limit with SMS provider', 'Investigate missing OTP email', 'Fix N+1 query on account listing'])
  })

  it('groups by due date', async () => {
    open('/tasks?group=due&status=open')
    await screen.findAllByRole('listitem')
    expect(groupHeadings()).toEqual(['Overdue', 'Due today', 'Next 7 days', 'Later', 'No due date'])
  })

  it('rows are 32px dense rows with the status control inline and the project beside the title when not grouped by it', async () => {
    open('/tasks?group=status&status=blocked')
    const row = (await screen.findByRole('link', { name: 'Confirm rate limit with SMS provider' })).closest('[aria-current], .min-h-8, div.grid')!
    expect(row.className).toContain('min-h-8')
    expect(within(row as HTMLElement).getByRole('button', { name: /Status: blocked/ })).toBeInTheDocument()
    expect(within(row as HTMLElement).getByText('LoadUp')).toBeInTheDocument()
  })
})

describe('TasksPage: status changes', () => {
  it('moving a task to done asks for evidence first, and writes it with the change', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    open('/tasks?status=open', client)
    await user.click(await screen.findByRole('button', { name: new RegExp(`Change status of ${ROTATE}`) }))
    await user.click(await screen.findByRole('menuitemradio', { name: 'done' }))
    const dialog = await screen.findByRole('dialog', { name: 'Mark as done' })
    expect((await client.lookupNote({ path: `02-Work/Tasks/${ROTATE}.md` })).status).toBe('planned')
    await user.type(within(dialog).getByLabelText(/Evidence/), 'Verified in staging')
    await user.click(within(dialog).getByRole('button', { name: 'Mark done' }))
    expect(await screen.findByRole('status')).toHaveTextContent(`Set status: done in 02-Work/Tasks/${ROTATE}.md`)
    const note = await client.lookupNote({ path: `02-Work/Tasks/${ROTATE}.md` })
    expect(note.status).toBe('done')
    expect(note.body).toContain('Verified in staging')
    // The list refetched: the task left the open list.
    await waitFor(() => expect(screen.queryByRole('link', { name: ROTATE })).toBeNull())
  })

  it('cancelling the done dialog changes nothing', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    const change = vi.spyOn(client, 'changeStatus')
    open('/tasks', client)
    await user.click(await screen.findByRole('button', { name: new RegExp(`Change status of ${ROTATE}`) }))
    await user.click(await screen.findByRole('menuitemradio', { name: 'done' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Cancel' }))
    expect(change).not.toHaveBeenCalled()
  })

  it('a 409 says the note changed in Obsidian and refetches the list', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    const list = vi.spyOn(client, 'listNotes')
    client.changeStatus = async () => {
      throw new ApiError(409, 'stale')
    }
    open('/tasks', client)
    await user.click(await screen.findByRole('button', { name: new RegExp(`Change status of ${ROTATE}`) }))
    const before = list.mock.calls.length
    await user.click(await screen.findByRole('menuitemradio', { name: 'review' }))
    expect(await screen.findByRole('status')).toHaveTextContent(`${ROTATE} changed in Obsidian, reloaded.`)
    await waitFor(() => expect(list.mock.calls.length).toBeGreaterThan(before))
    expect(await screen.findByRole('button', { name: new RegExp(`Status: planned. Change status of ${ROTATE}`) })).toBeInTheDocument()
  })
})

describe('TasksPage: opening a note', () => {
  it('at 1024 and up a plain click opens the reader beside the list and records the note in the URL', async () => {
    const user = userEvent.setup()
    const { router } = open('/tasks?status=open', mockClient(), 1024)
    await user.click(await screen.findByRole('link', { name: ROTATE }))
    const pane = await screen.findByRole('complementary', { name: 'Open note' })
    expect(await within(pane).findByRole('heading', { name: ROTATE })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/tasks')
    expect(search(router).get('note')).toBe(`02-Work/Tasks/${ROTATE}.md`)
    expect(search(router).get('status')).toBe('open')
    expect(screen.getByRole('link', { name: ROTATE }).closest('[aria-current="true"]')).not.toBeNull()
    // Filters still work while the reader is open, and it stays.
    await user.click(screen.getByRole('button', { name: /^blocked 2$/ }))
    expect(search(router).get('note')).toBe(`02-Work/Tasks/${ROTATE}.md`)
    await user.click(within(pane).getByRole('button', { name: 'Close note' }))
    expect(search(router).has('note')).toBe(false)
    expect(screen.queryByRole('complementary')).toBeNull()
  })

  it('the reader in the pane reloads the list when its status changes', async () => {
    const user = userEvent.setup()
    open(`/tasks?status=planned&note=${encodeURIComponent(`02-Work/Tasks/${ROTATE}.md`)}`, mockClient(), 1440)
    const pane = await screen.findByRole('complementary', { name: 'Open note' })
    await user.click(await within(pane).findByRole('button', { name: /Status: planned/ }))
    await user.click(await screen.findByRole('menuitemradio', { name: 'in-progress' }))
    await waitFor(() => expect(screen.queryByRole('link', { name: ROTATE, description: '' })).toBeNull())
  })

  it('below 1024 the title is a link to the note route and there is no pane', async () => {
    const user = userEvent.setup()
    const { router } = open('/tasks', mockClient(), 800)
    await user.click(await screen.findByRole('link', { name: ROTATE }))
    expect(router.state.location.pathname).toBe('/notes')
    expect(search(router).get('path')).toBe(`02-Work/Tasks/${ROTATE}.md`)
    expect(await screen.findByRole('heading', { name: ROTATE })).toBeInTheDocument()
  })

  it('ignores a note parameter where there is no room for the pane', async () => {
    open(`/tasks?note=${encodeURIComponent(`02-Work/Tasks/${ROTATE}.md`)}`, mockClient(), 800)
    await screen.findAllByRole('listitem')
    expect(screen.queryByRole('complementary')).toBeNull()
  })
})

describe('TasksPage: phone', () => {
  it('rows have two lines with the due date under the title', async () => {
    open('/tasks?status=planned', mockClient(), 390)
    await screen.findAllByRole('listitem')
    const row = screen.getByRole('link', { name: ROTATE }).closest('div.grid')!
    expect(row.className).toContain('min-h-12')
    expect(row).toHaveTextContent('Overdue, Oct 3')
    const none = screen.getByRole('link', { name: 'Draft Phase 1 README run instructions' }).closest('div.grid')!
    expect(none).toHaveTextContent('No due date')
  })
})

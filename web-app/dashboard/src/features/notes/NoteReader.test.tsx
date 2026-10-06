import { configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/api/client'
import type { NoteDetail } from '@/api/types'
import { mockClient } from '@/test/helpers'
import { NotePage } from './NotePage'
import { NoteReader } from './NoteReader'
import { renderRoutes } from './testing'

// The suite shares a slow WSL mount with other work; findBy's default 1s is too tight there.
configure({ asyncUtilTimeout: 5000 })

const TASK = '02-Work/Tasks/Rotate staging API credentials.md'
const routes = [
  { path: '/notes', element: <NotePage /> },
  { path: '/other', element: <NoteReader path={TASK} /> },
]
const open = (path: string, client = mockClient()) => renderRoutes(routes, `/notes?path=${encodeURIComponent(path)}`, client)

describe('NoteReader', () => {
  it('shows title, type, status, priority, due, project, dates and path', async () => {
    open(TASK)
    expect(await screen.findByRole('heading', { name: 'Rotate staging API credentials' })).toBeInTheDocument()
    expect(screen.getByText('task')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Status: planned/ })).toBeInTheDocument()
    const fields = screen.getByText('Priority').closest('dl')!
    expect(within(fields).getByText('High priority')).toBeInTheDocument()
    expect(within(fields).getByText('Overdue, Oct 3')).toBeInTheDocument()
    expect(await within(fields).findByRole('link', { name: 'LoadUp' })).toHaveAttribute('href', '/projects/loadup')
    expect(within(fields).getByText('Sep 29')).toBeInTheDocument()
    expect(within(fields).getByText(TASK)).toBeInTheDocument()
  })

  it('shows N/A for missing fields and an unknown project as such', async () => {
    open('02-Work/Tasks/Clarify OTP expiry requirement.md')
    const fields = (await screen.findByText('Priority')).closest('dl')!
    expect(within(fields).getAllByText('N/A').length).toBeGreaterThanOrEqual(3)
    expect(await within(fields).findByText('loadup-v2 (unknown)')).toBeInTheDocument()
  })

  it('renders raw HTML in the body as text', async () => {
    const client = mockClient()
    const real = client.lookupNote
    client.lookupNote = async (by) => ({ ...(await real(by)), body: '<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>' })
    const { container } = open(TASK, client)
    await screen.findByRole('heading', { name: 'Rotate staging API credentials' })
    expect(container.querySelector('script, img, [onerror]')).toBeNull()
    expect(container).toHaveTextContent('<script>alert(1)</script>')
    expect(container).toHaveTextContent('onerror=alert(1)')
  })

  it('links a body wikilink and lists backlinks as in-app links', async () => {
    const client = mockClient()
    const real = client.lookupNote
    client.lookupNote = async (by) => ({
      ...(await real(by)),
      body: 'Related: [[LoadUp]]',
      links: { LoadUp: { path: '02-Work/Projects/LoadUp.md', state: 'resolved' } },
      backlinks: [{ path: '02-Work/Projects/LoadUp.md', title: 'LoadUp project note' }],
    })
    open(TASK, client)
    await screen.findByRole('heading', { name: 'Rotate staging API credentials' })
    // The project field also links "LoadUp" (to the project page, once the project list loads); the body link goes to the note.
    const hrefs = screen.getAllByRole('link', { name: 'LoadUp' }).map((a) => a.getAttribute('href'))
    expect(hrefs).toContain('/notes?path=02-Work%2FProjects%2FLoadUp.md')
    const backlinks = screen.getByRole('region', { name: 'Backlinks' })
    expect(within(backlinks).getByRole('link', { name: 'LoadUp project note' })).toHaveAttribute('href', '/notes?path=02-Work%2FProjects%2FLoadUp.md')
  })

  it('says when nothing links here', async () => {
    const client = mockClient()
    const real = client.lookupNote
    client.lookupNote = async (by) => ({ ...(await real(by)), backlinks: [] })
    open(TASK, client)
    expect(await screen.findByText('No other note links here.')).toBeInTheDocument()
  })

  it('shows a parse error and offers no status change', async () => {
    const client = mockClient()
    const real = client.lookupNote
    client.lookupNote = async (by): Promise<NoteDetail> => ({ ...(await real(by)), parse_error: 'Frontmatter: mapping values are not allowed here (line 3).' })
    open(TASK, client)
    expect(await screen.findByRole('alert')).toHaveTextContent('mapping values are not allowed here (line 3)')
    expect(screen.queryByRole('button', { name: /Change status/ })).toBeNull()
  })

  it('asks for evidence when marking a task done and writes it under Notes', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    open(TASK, client)
    await user.click(await screen.findByRole('button', { name: /Status: planned/ }))
    await user.click(await screen.findByRole('menuitemradio', { name: 'done' }))
    const dialog = await screen.findByRole('dialog', { name: 'Mark as done' })
    await user.type(within(dialog).getByLabelText(/Evidence/), 'Rotated in staging, verified login')
    await user.click(within(dialog).getByRole('button', { name: 'Mark done' }))
    expect(await screen.findByRole('status')).toHaveTextContent(`Set status: done in ${TASK}`)
    await waitFor(async () => expect((await client.lookupNote({ path: TASK })).body).toContain('Rotated in staging, verified login'))
    // The reader refetched: the new status and the evidence are on screen.
    expect(await screen.findByRole('button', { name: /Status: done/ })).toBeInTheDocument()
    expect(await screen.findByText(/Rotated in staging, verified login/)).toBeInTheDocument()
  })

  it('on a 409 says the note changed in Obsidian and refetches it', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    const lookup = vi.spyOn(client, 'lookupNote')
    client.changeStatus = async () => {
      throw new ApiError(409, 'changed')
    }
    open(TASK, client)
    await user.click(await screen.findByRole('button', { name: /Status: planned/ }))
    const calls = lookup.mock.calls.length
    await user.click(await screen.findByRole('menuitemradio', { name: 'review' }))
    expect(await screen.findByRole('status')).toHaveTextContent('changed in Obsidian, reloaded')
    await waitFor(() => expect(lookup.mock.calls.length).toBeGreaterThan(calls))
    expect(await screen.findByRole('button', { name: /Status: planned/ })).toBeInTheDocument()
  })

  it('shows an error with a retry for an unknown note', async () => {
    open('02-Work/Tasks/Nope.md')
    expect(await screen.findByRole('alert')).toHaveTextContent('No note at 02-Work/Tasks/Nope.md.')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('shows a loading state, then the note', async () => {
    open(TASK)
    expect(screen.getByText('Loading')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Rotate staging API credentials' })).toBeInTheDocument()
  })

  it('the route says what to do when no path is given', () => {
    renderRoutes(routes, '/notes')
    expect(screen.getByText(/No note is selected/)).toBeInTheDocument()
  })

  it('the close button calls onClose', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    renderRoutes([{ path: '/x', element: <NoteReader path={TASK} onClose={onClose} /> }], '/x')
    await user.click(await screen.findByRole('button', { name: 'Close note' }))
    expect(onClose).toHaveBeenCalled()
  })
})

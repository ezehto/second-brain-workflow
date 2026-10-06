import { configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '@/api/client'
import { NotePage } from '@/features/notes/NotePage'
import { renderRoutes } from '@/features/notes/testing'
import { mockClient } from '@/test/helpers'
import { DecisionsPage, KnowledgePage } from './index'
import { groupDecisions } from './filters'

configure({ asyncUtilTimeout: 5000 })

const routes = [
  { path: '/knowledge', element: <KnowledgePage /> },
  { path: '/decisions', element: <DecisionsPage /> },
  { path: '/notes', element: <NotePage /> },
]
const open = (url: string, client: ApiClient = mockClient(), width = 1440) => renderRoutes(routes, url, client, width)
const search = (router: { state: { location: { search: string } } }) => new URLSearchParams(router.state.location.search)
const rowTitles = () => screen.getAllByRole('listitem').map((li) => within(li).getAllByRole('link')[0].textContent)
const spy = (client: ApiClient) => {
  const listNotes = vi.spyOn(client, 'listNotes')
  return listNotes
}
const failing = (client: ApiClient) => {
  const real = client.listNotes
  let fail = true
  client.listNotes = async (p) => {
    if (fail) throw new Error('Network down')
    return real(p)
  }
  return () => (fail = false)
}

describe('KnowledgePage', () => {
  it('lists type=lesson, newest change first, with project, tags and date', async () => {
    const client = mockClient()
    const listNotes = spy(client)
    open('/knowledge', client)
    expect(screen.getByText('Loading')).toBeInTheDocument()
    await screen.findAllByRole('listitem')
    expect(listNotes.mock.calls[0][0]).toMatchObject({ type: 'lesson' })
    expect(rowTitles()).toEqual([
      'A retry on a business rejection duplicates the send',
      'Measure the mount before building on it',
      'Check the provider status page before debugging delivery',
    ])
    const first = screen.getAllByRole('listitem')[0]
    expect(first).toHaveTextContent('payments, retries')
    expect(screen.getByRole('heading', { level: 2, name: 'Lessons' })).toBeInTheDocument()
  })

  it('filters by the project parameter and by tag, and writes the tag to the URL', async () => {
    const user = userEvent.setup()
    const { router } = open('/knowledge?project=ipp')
    await screen.findAllByRole('listitem')
    expect(rowTitles()).toEqual(['A retry on a business rejection duplicates the send'])
    await user.click(screen.getByRole('button', { name: 'payments' }))
    expect(search(router).get('tag')).toBe('payments')
    expect(search(router).get('project')).toBe('ipp')
  })

  it('shows only the tags present and filters by one', async () => {
    const user = userEvent.setup()
    open('/knowledge?tag=docker')
    await screen.findAllByRole('listitem')
    expect(rowTitles()).toEqual(['Measure the mount before building on it'])
    const group = screen.getByRole('group', { name: 'Filter by tag' })
    expect(within(group).getAllByRole('button').map((b) => b.textContent)).toEqual(['All tags', 'docker', 'email', 'incident', 'payments', 'retries', 'wsl'])
    await user.click(within(group).getByRole('button', { name: 'All tags' }))
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
  })

  it('the status segments map to ?status= and a stale value is ignored', async () => {
    const user = userEvent.setup()
    const { router } = open('/knowledge?status=bogus')
    await screen.findAllByRole('listitem')
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
    await user.click(screen.getByRole('button', { name: 'archived' }))
    expect(search(router).get('status')).toBe('archived')
    expect(await screen.findByText('No lessons match these filters.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Clear filters' })).toHaveAttribute('href', '/knowledge')
  })

  it('opens the reader on a row at 1440, and links to the note route below 1024', async () => {
    const user = userEvent.setup()
    const { router, unmount } = open('/knowledge')
    await user.click(await screen.findByRole('link', { name: 'Measure the mount before building on it' }))
    expect(search(router).get('note')).toBe('05-Knowledge/Lessons/Measure the mount before building on it.md')
    expect(await screen.findByRole('complementary', { name: 'Open note' })).toBeInTheDocument()
    unmount()

    open('/knowledge', mockClient(), 800)
    const link = await screen.findByRole('link', { name: 'Measure the mount before building on it' })
    expect(link.getAttribute('href')).toBe('/notes?path=05-Knowledge%2FLessons%2FMeasure%20the%20mount%20before%20building%20on%20it.md')
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
  })

  it('says what to do when there are no lessons', async () => {
    const client = mockClient()
    client.listNotes = async () => ({ count: 0, next: null, previous: null, results: [] })
    open('/knowledge', client)
    expect(await screen.findByText(/No lessons yet/)).toBeInTheDocument()
  })

  it('shows an error with a retry', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    const recover = failing(client)
    open('/knowledge', client)
    expect(await screen.findByRole('alert')).toHaveTextContent('Network down')
    recover()
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findAllByRole('listitem')).toHaveLength(3)
  })
})

describe('DecisionsPage', () => {
  it('lists type=decision grouped by status with proposed first, and N/A for no decided date', async () => {
    const client = mockClient()
    const listNotes = spy(client)
    open('/decisions', client)
    await screen.findAllByRole('listitem')
    expect(listNotes.mock.calls[0][0]).toMatchObject({ type: 'decision' })
    expect(screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['Proposed', 'Accepted', 'Superseded'])
    expect(screen.getByRole('region', { name: 'Accepted' })).toHaveTextContent('Decisions: 2')
    const proposed = screen.getAllByRole('listitem')[0]
    expect(proposed).toHaveTextContent('Use idempotency keys on payment callbacks')
    expect(proposed).toHaveTextContent('N/A')
  })

  it('shows a count per status in the segments', async () => {
    open('/decisions')
    await screen.findAllByRole('listitem')
    const group = screen.getByRole('group', { name: 'Filter by status' })
    expect(within(group).getAllByRole('button').map((b) => b.textContent)).toEqual(['All 4', 'proposed 1', 'accepted 2', 'superseded 1', 'rejected 0'])
  })

  it('a status segment writes ?status= and narrows to that group', async () => {
    const user = userEvent.setup()
    const { router } = open('/decisions')
    await screen.findAllByRole('listitem')
    await user.click(screen.getByRole('button', { name: 'accepted 2' }))
    expect(search(router).get('status')).toBe('accepted')
    await waitFor(() => expect(screen.getAllByRole('listitem')).toHaveLength(2))
    expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(1)
  })

  it('?status=rejected shows an empty state with a way out, and the project parameter narrows the counts', async () => {
    open('/decisions?status=rejected')
    expect(await screen.findByText('No decisions match these filters.')).toBeInTheDocument()
  })

  it('the project parameter filters the list and the counts', async () => {
    open('/decisions?project=ipp')
    await screen.findAllByRole('listitem')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(within(screen.getByRole('group', { name: 'Filter by status' })).getByRole('button', { name: 'All 2' })).toBeInTheDocument()
  })

  it('changes a decision status in place and names the file', async () => {
    const user = userEvent.setup()
    open('/decisions')
    await user.click(await screen.findByRole('button', { name: /Change status of Use idempotency keys/ }))
    await user.click(await screen.findByRole('menuitemradio', { name: 'accepted' }))
    expect(await screen.findByText(/Set status: accepted in 05-Knowledge\/Decisions\/Use idempotency keys on payment callbacks\.md/)).toBeInTheDocument()
    const menu = await screen.findAllByRole('button', { name: /Change status of Use idempotency keys/ })
    await waitFor(() => expect(menu[0]).toHaveAccessibleName(/Status: accepted/))
  })

  it('opens the reader with the note on a row click', async () => {
    const user = userEvent.setup()
    const { router } = open('/decisions')
    await user.click(await screen.findByRole('link', { name: 'Poll the vault instead of file watching' }))
    expect(search(router).get('note')).toBe('05-Knowledge/Decisions/Poll the vault instead of file watching.md')
    const pane = await screen.findByRole('complementary', { name: 'Open note' })
    expect(await within(pane).findByRole('heading', { name: 'Poll the vault instead of file watching' })).toBeInTheDocument()
  })

  it('says what to do when the vault has no decisions', async () => {
    const client = mockClient()
    client.listNotes = async () => ({ count: 0, next: null, previous: null, results: [] })
    open('/decisions', client)
    expect(await screen.findByText(/No decisions yet/)).toBeInTheDocument()
  })

  it('shows an error with a retry', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    const recover = failing(client)
    open('/decisions', client)
    expect(await screen.findByRole('alert')).toHaveTextContent('Network down')
    recover()
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findAllByRole('listitem')).toHaveLength(4)
  })
})

describe('groupDecisions', () => {
  it('orders by vocabulary and puts an unrecognised status last', () => {
    const d = (status: string | null, n: string) => ({ path: n, title: n, status }) as never
    const groups = groupDecisions([d('rejected', 'a'), d('weird', 'b'), d('proposed', 'c'), d(null, 'e')])
    expect(groups.map((g) => g.label)).toEqual(['Proposed', 'Rejected', 'No recognised status'])
    expect(groups[2].decisions).toHaveLength(2)
  })
})

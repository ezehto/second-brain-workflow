import { configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/api/client'
import type { ApiClient } from '@/api/client'
import type { SearchResult } from '@/api/types'
import { renderRoutes } from '@/features/notes/testing'
import { mockClient } from '@/test/helpers'
import { splitMatches } from './Highlight'
import { SearchPage } from './SearchPage'

configure({ asyncUtilTimeout: 5000 })

const RETRY = '02-Work/Tasks/Add retry with backoff to payment callback handler.md'
const hit = (over: Partial<SearchResult> = {}): SearchResult => ({
  path: RETRY,
  type: 'task',
  title: 'Add retry with backoff to payment callback handler',
  snippet: 'Callbacks that fail should retry with exponential backoff.',
  source: 'vault',
  ...over,
})
const HITS = [
  hit(),
  hit({ path: '05-Knowledge/Lessons/Retry only idempotent calls.md', type: 'lesson', title: 'Retry only idempotent calls', snippet: 'A retry of a payment call can send it twice.' }),
  hit({ path: '05-Knowledge/Decisions/Use exponential retry.md', type: 'decision', title: 'Use exponential retry', snippet: 'Retry intervals double up to a cap.' }),
]

const clientWith = (search: ApiClient['search']): ApiClient => ({ ...mockClient(), search })
const routes = [
  { path: '/search', element: <SearchPage /> },
  { path: '/notes', element: <p>reader route</p> },
]
const open = (url: string, client: ApiClient = mockClient(), width = 1440) => renderRoutes(routes, url, client, width)

describe('SearchPage', () => {
  it('shows a hint and the ten most recently modified notes when the query is empty', async () => {
    open('/search')
    expect(screen.getByLabelText('Search the vault')).toHaveValue('')
    expect(screen.getByText(/Type above to search the vault/)).toBeInTheDocument()
    const list = (await screen.findByText('Investigate missing OTP email')).closest('ul')!
    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(10)
    expect(items[0]).toHaveTextContent('Should the standup list show week numbers?')
  })

  it('pre-fills the input from q and shows type, title, snippet, project, path and source on every row', async () => {
    open('/search?q=retry', clientWith(async (q) => ({ query: q, results: HITS })))
    expect(screen.getByLabelText('Search the vault')).toHaveValue('retry')
    expect(await screen.findByText('3 results for "retry" in the vault')).toBeInTheDocument()
    const rows = screen.getAllByRole('listitem')
    expect(rows).toHaveLength(3)
    const first = rows[0]
    expect(within(first).getByText('task')).toBeInTheDocument()
    expect(within(first).getByRole('button', { name: 'Add retry with backoff to payment callback handler' })).toBeInTheDocument()
    expect(within(first).getByText('Callbacks that fail should', { exact: false })).toBeInTheDocument()
    expect(within(first).getByText(RETRY)).toHaveClass('mono')
    expect(await within(first).findByText('IPP')).toBeInTheDocument()
    for (const row of rows) expect(within(row).getByText('source: vault')).toBeInTheDocument()
  })

  it('marks the match by wrapping text, and never renders a snippet as HTML', async () => {
    const snippet = 'retry <img src=x onerror=alert(1)> and <b>bold</b>'
    open('/search?q=retry', clientWith(async (q) => ({ query: q, results: [hit({ snippet })] })))
    const row = (await screen.findAllByRole('listitem'))[0]
    expect(row.querySelector('mark')).toHaveTextContent(/^retry$/i)
    expect(row.querySelector('img')).toBeNull()
    expect(row.querySelector('b')).toBeNull()
    expect(row).toHaveTextContent('<img src=x onerror=alert(1)>')
  })

  it('splits text on the query words, case-insensitively and with regex characters escaped', () => {
    expect(splitMatches('Retry the Retry (now)', 'retry')).toEqual([
      { text: 'Retry', match: true },
      { text: ' the ', match: false },
      { text: 'Retry', match: true },
      { text: ' (now)', match: false },
    ])
    expect(splitMatches('call f(x) twice', 'f(x')).toEqual([
      { text: 'call ', match: false },
      { text: 'f(x', match: true },
      { text: ') twice', match: false },
    ])
    expect(splitMatches('plain', '   ')).toEqual([{ text: 'plain', match: false }])
  })

  it('debounces typing into one request and writes the query to the URL', async () => {
    const user = userEvent.setup()
    const search = vi.fn(async (q: string) => ({ query: q, results: HITS }))
    const { router } = open('/search', clientWith(search))
    await user.type(screen.getByLabelText('Search the vault'), 'retry')
    expect(search).not.toHaveBeenCalled()
    expect(router.state.location.search).toBe('')
    await waitFor(() => expect(router.state.location.search).toBe('?q=retry'))
    await screen.findByText('3 results for "retry" in the vault')
    expect(search).toHaveBeenCalledTimes(1)
    expect(search).toHaveBeenCalledWith('retry')
  })

  it('follows the URL when it changes from elsewhere', async () => {
    const { router } = open('/search?q=retry', clientWith(async (q) => ({ query: q, results: HITS })))
    await screen.findByText('3 results for "retry" in the vault')
    await router.navigate('/search?q=callback')
    await waitFor(() => expect(screen.getByLabelText('Search the vault')).toHaveValue('callback'))
    expect(await screen.findByText('3 results for "callback" in the vault')).toBeInTheDocument()
  })

  it('filters by type with a count per type, kept in the URL', async () => {
    const user = userEvent.setup()
    const { router } = open('/search?q=retry', clientWith(async (q) => ({ query: q, results: HITS })))
    await screen.findByText('3 results for "retry" in the vault')
    const group = screen.getByRole('group', { name: 'Filter by note type' })
    expect(within(group).getAllByRole('button').map((b) => b.textContent)).toEqual(['All (3)', 'decision (1)', 'lesson (1)', 'task (1)'])
    await user.click(within(group).getByRole('button', { name: 'lesson (1)' }))
    expect(router.state.location.search).toContain('type=lesson')
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
    expect(screen.getByText('Retry only idempotent calls')).toBeInTheDocument()
  })

  it('says so when nothing matches and offers to remove the type filter', async () => {
    const user = userEvent.setup()
    const { router } = open('/search?q=zzz&type=lesson', clientWith(async (q) => ({ query: q, results: [] })))
    expect(await screen.findByText('0 results for "zzz" in the vault')).toBeInTheDocument()
    expect(screen.getByText(/No notes match/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Remove the type filter' }))
    expect(router.state.location.search).not.toContain('type=')
  })

  it('shows an error with a retry that asks again', async () => {
    const user = userEvent.setup()
    const search = vi.fn<ApiClient['search']>().mockRejectedValueOnce(new ApiError(500, 'The index is down.')).mockResolvedValue({ query: 'retry', results: HITS })
    open('/search?q=retry', clientWith(search))
    expect(await screen.findByRole('alert')).toHaveTextContent('The index is down.')
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('3 results for "retry" in the vault')).toBeInTheDocument()
  })

  it('opens a result in the split pane at wide widths', async () => {
    const user = userEvent.setup()
    open('/search?q=retry', clientWith(async (q) => ({ query: q, results: HITS })), 1440)
    await user.click(await screen.findByRole('button', { name: 'Add retry with backoff to payment callback handler' }))
    const pane = await screen.findByRole('complementary', { name: 'Note' })
    expect(await within(pane).findByRole('heading', { name: 'Add retry with backoff to payment callback handler' })).toBeInTheDocument()
  })

  it('links a result to the reader route on a narrow screen, keeping the project', async () => {
    open('/search?q=retry&project=ipp', clientWith(async (q) => ({ query: q, results: HITS })), 700)
    const link = await screen.findByRole('link', { name: 'Add retry with backoff to payment callback handler' })
    const href = new URL(link.getAttribute('href')!, 'http://x')
    expect(href.pathname).toBe('/notes')
    expect(href.searchParams.get('path')).toBe(RETRY)
    expect(href.searchParams.get('project')).toBe('ipp')
  })

  it('limits results to the project context', async () => {
    open('/search?q=retry&project=loadup', clientWith(async (q) => ({ query: q, results: HITS })))
    expect(await screen.findByText(/No notes match|Nothing in this project matches/)).toBeInTheDocument()
    expect(screen.queryByText('Add retry with backoff to payment callback handler')).toBeNull()
  })

  it('waits for the note list before saying nothing matches in a project, and shows its error', async () => {
    let release: () => void = () => {}
    const client = clientWith(async (q) => ({ query: q, results: HITS }))
    const list = client.listNotes
    client.listNotes = (params) => new Promise((resolve) => (release = () => resolve(list(params))))
    const a = open('/search?q=retry&project=ipp', client)
    await screen.findByText('Loading')
    expect(screen.queryByText(/Nothing in this project matches/)).not.toBeInTheDocument()
    release()
    expect(await screen.findByText(/results? for "retry" in the vault/)).toBeInTheDocument()
    a.unmount()

    const failing = clientWith(async (q) => ({ query: q, results: HITS }))
    failing.listNotes = () => Promise.reject(new Error('Notes failed'))
    open('/search?q=retry&project=ipp', failing)
    expect(await screen.findByRole('alert')).toHaveTextContent('Notes failed')
  })
})

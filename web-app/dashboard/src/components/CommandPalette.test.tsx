import { configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '@/api/client'
import { createMemoryRouter } from 'react-router'
import { render } from '@testing-library/react'
import { App } from '@/App'
import { fixedClock } from '@/lib/clock'
import { createRoutes } from '@/routes'
import { mockClient, renderApp, TODAY } from '@/test/helpers'

configure({ asyncUtilTimeout: 5000 })

const RETRY = '02-Work/Tasks/Add retry with backoff to payment callback handler.md'
const withSearch = (search: ApiClient['search']): ApiClient => ({ ...mockClient(), search })
const ctrlK = (user: ReturnType<typeof userEvent.setup>) => user.keyboard('{Control>}k{/Control}')

async function openPalette(path = '/', client: ApiClient = mockClient()) {
  const user = userEvent.setup()
  const router = createMemoryRouter(createRoutes({ sampleData: true }), { initialEntries: [path] })
  const view = render(<App client={client} clock={fixedClock(TODAY)} router={router} />)
  await screen.findByRole('searchbox', { name: 'Search the vault' })
  await ctrlK(user)
  const dialog = await screen.findByRole('dialog', { name: 'Command palette' })
  return { user, dialog, router, ...view }
}

describe('CommandPalette', () => {
  it('opens on Ctrl+K from anywhere and lists the destinations and quick actions under Go to', async () => {
    const { dialog } = await openPalette()
    const input = within(dialog).getByRole('combobox', { name: 'Search commands and notes' })
    expect(input).toHaveFocus()
    expect(within(dialog).getByText('Go to')).toBeInTheDocument()
    const names = within(dialog).getAllByRole('option').map((o) => o.textContent)
    expect(names).toEqual(expect.arrayContaining(['Tasks', 'Search', 'Index status', 'New task', 'New capture']))
  })

  it('filters the commands by the typed text', async () => {
    const { user, dialog } = await openPalette()
    await user.type(within(dialog).getByRole('combobox'), 'capt')
    await waitFor(() => expect(within(dialog).getAllByRole('option').map((o) => o.textContent)).toEqual(['New capture']))
  })

  it('shows matching notes from search, at most eight, after the typing pauses', async () => {
    const results = Array.from({ length: 12 }, (_, i) => ({
      path: `02-Work/Tasks/Retry ${i}.md`,
      type: 'task',
      title: `Retry ${i}`,
      snippet: 'x',
      source: 'vault' as const,
    }))
    const search = vi.fn(async (q: string) => ({ query: q, results }))
    const { user, dialog } = await openPalette('/', withSearch(search))
    await user.type(within(dialog).getByRole('combobox'), 'retry')
    expect(search).not.toHaveBeenCalled()
    const notes = await within(dialog).findByText('Retry 0')
    expect(notes).toBeInTheDocument()
    expect(within(dialog).getAllByRole('option').filter((o) => /^task/.test(o.textContent ?? ''))).toHaveLength(8)
    expect(search).toHaveBeenCalledTimes(1)
    expect(within(dialog).getByText('Notes')).toBeInTheDocument()
  })

  it('moves with the arrow keys and opens the chosen note on Enter, keeping the project', async () => {
    const search = async (q: string) => ({
      query: q,
      results: [{ path: RETRY, type: 'task', title: 'Add retry with backoff to payment callback handler', snippet: 'x', source: 'vault' as const }],
    })
    const { user, dialog, router } = await openPalette('/tasks?project=ipp', withSearch(search))
    const input = within(dialog).getByRole('combobox')
    await user.type(input, 'retry')
    await within(dialog).findByText('Add retry with backoff to payment callback handler')
    // No page or action is named "retry", so the note is the only option and ArrowDown wraps back to it.
    await user.keyboard('{ArrowDown}')
    const option = within(dialog).getByRole('option', { selected: true })
    expect(input).toHaveAttribute('aria-activedescendant', option.id)
    await user.keyboard('{Enter}')
    await waitFor(() => expect(router.state.location.pathname).toBe('/notes'))
    const params = new URLSearchParams(router.state.location.search)
    expect(params.get('path')).toBe(RETRY)
    expect(params.get('project')).toBe('ipp')
    expect(screen.queryByRole('dialog', { name: 'Command palette' })).toBeNull()
  })

  it('navigates to a destination on Enter and keeps the project parameter', async () => {
    const { user, dialog, router } = await openPalette('/?project=loadup')
    await user.type(within(dialog).getByRole('combobox'), 'index')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(router.state.location.pathname).toBe('/index-status'))
    expect(router.state.location.search).toBe('?project=loadup')
  })

  it('starts a quick action through the quick-action dialog', async () => {
    const { user, dialog } = await openPalette()
    await user.type(within(dialog).getByRole('combobox'), 'new task')
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('dialog', { name: 'Create task' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: 'Command palette' })).toBeNull()
  })

  it('closes on Escape and returns focus to where it was', async () => {
    const user = userEvent.setup()
    renderApp('/')
    const box = await screen.findByRole('searchbox', { name: 'Search the vault' })
    await user.click(box)
    await ctrlK(user)
    await screen.findByRole('dialog', { name: 'Command palette' })
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Command palette' })).toBeNull())
    await waitFor(() => expect(box).toHaveFocus())
  })

  it('says when a search for notes fails, and keeps the commands usable', async () => {
    const search = vi.fn().mockRejectedValue(new Error('The index is down.'))
    const { user, dialog } = await openPalette('/', withSearch(search))
    await user.type(within(dialog).getByRole('combobox'), 'tasks')
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('The index is down.')
    expect(within(dialog).getByRole('option', { name: 'Tasks' })).toBeInTheDocument()
  })
})

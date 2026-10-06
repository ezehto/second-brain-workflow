import { configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ApiError } from '@/api/client'
import type { ApiClient } from '@/api/client'
import type { NoteDetail, TriageRequest } from '@/api/types'
import { NotePage } from '@/features/notes/NotePage'
import { renderRoutes } from '@/features/notes/testing'
import { mockClient } from '@/test/helpers'
import { InboxPage } from './InboxPage'

configure({ asyncUtilTimeout: 5000 })

const routes = [
  { path: '/inbox', element: <InboxPage /> },
  { path: '/notes', element: <NotePage /> },
]
const open = (client: ApiClient = mockClient(), width = 1440, url = '/inbox') => renderRoutes(routes, url, client, width)

const TLS = 'todo: renew the staging TLS certificate before the 20th'
const IDEMPOTENCY = 'Idempotency keys on the callback handler would have prevented the duplicate rows'
const rowOf = (name: string) => within(screen.getByRole('listitem', { name: new RegExp(name.slice(0, 20)) }))

/** Overrides the classification a capture carries, to cover states the fixtures do not (`classified` maps a text prefix to a kind). */
function withBodies(client: ApiClient, classified: Record<string, string> = {}) {
  const lookup = client.lookupNote.bind(client)
  client.lookupNote = async (by) => {
    const note = await lookup(by)
    const kind = Object.entries(classified).find(([k]) => note.body.startsWith(k))?.[1]
    return (kind ? { ...note, frontmatter: { ...note.frontmatter, classification: kind } } : note) as NoteDetail
  }
  return client
}

function spyTriage(client: ApiClient) {
  const calls: TriageRequest[] = []
  const real = client.triageCapture.bind(client)
  client.triageCapture = async (input) => {
    calls.push(input)
    return real(input)
  }
  return calls
}

describe('InboxPage: what it lists', () => {
  it('lists only status: inbox captures, newest first, and not other notes or triaged captures', async () => {
    const client = withBodies(mockClient())
    const done = await client.listNotes({ type: 'capture' })
    expect(done.results).toHaveLength(4)
    open(client)
    expect(screen.getByText('Loading')).toBeInTheDocument()
    await screen.findByRole('list', { name: 'Captures awaiting triage' })
    const names = screen.getAllByRole('listitem').map((li) => li.getAttribute('aria-label'))
    expect(names).toEqual(['Should the standup list show week numbers?', IDEMPOTENCY, expect.stringContaining('decided to keep the OTP sender'), TLS])
    expect(screen.queryByText('Rotate staging API credentials')).not.toBeInTheDocument()
  })

  it('drops a capture whose status is not inbox', async () => {
    const client = withBodies(mockClient())
    const lookup = client.lookupNote.bind(client)
    client.lookupNote = async (by) => {
      const n = await lookup(by)
      return n.title.includes('week numbers') ? { ...n, status: 'triaged' } : n
    }
    open(client)
    await screen.findAllByRole('listitem')
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
  })

  it('shows Inbox clear with the capture field still available', async () => {
    const client = mockClient()
    client.listNotes = async () => ({ count: 0, next: null, previous: null, results: [] })
    open(client)
    expect(await screen.findByText(/Inbox clear/)).toBeInTheDocument()
    expect(screen.getByLabelText('Quick capture')).toBeInTheDocument()
  })

  it('shows an error with a retry', async () => {
    const user = userEvent.setup()
    const client = withBodies(mockClient())
    const real = client.listNotes
    let fail = true
    client.listNotes = async (p) => {
      if (fail) throw new Error('Network down')
      return real(p)
    }
    open(client)
    expect(await screen.findByRole('alert')).toHaveTextContent('Network down')
    fail = false
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findAllByRole('listitem')).toHaveLength(4)
  })
})

describe('InboxPage: project context', () => {
  const emptyClient = () => {
    const client = mockClient()
    client.listNotes = async () => ({ count: 0, next: null, previous: null, results: [] })
    return client
  }
  it('says the project filter does not apply, only when the inbox is clear and a project is selected', async () => {
    const { unmount } = open(emptyClient(), 1440, '/inbox?project=ipp')
    expect(await screen.findByText(/project filter does not apply/)).toBeInTheDocument()
    unmount()
    open(emptyClient())
    await screen.findByText(/Inbox clear/)
    expect(screen.queryByText(/project filter does not apply/)).not.toBeInTheDocument()
  })
})

describe('InboxPage: quick capture', () => {
  it('posts the text and the new item appears', async () => {
    const user = userEvent.setup()
    const client = withBodies(mockClient())
    const posted: string[] = []
    const real = client.createCapture.bind(client)
    client.createCapture = async (input) => {
      posted.push(input.text)
      return real(input)
    }
    open(client)
    await screen.findAllByRole('listitem')
    await user.type(screen.getByLabelText('Quick capture'), 'Call the bank back')
    await user.click(screen.getByRole('button', { name: 'Capture' }))
    expect(posted).toEqual(['Call the bank back'])
    expect(await screen.findByRole('listitem', { name: 'Call the bank back' })).toBeInTheDocument()
    expect(screen.getByLabelText('Quick capture')).toHaveValue('')
    expect(screen.getAllByText(/Captured in 00-Inbox\//).length).toBeGreaterThan(0)
  })

  it('does not post blank text', async () => {
    open(withBodies(mockClient()))
    await screen.findAllByRole('listitem')
    expect(screen.getByRole('button', { name: 'Capture' })).toBeDisabled()
  })
})

describe('InboxPage: the triage control', () => {
  it('offers the ten classifications and, with none chosen, no conversion yet', async () => {
    open(withBodies(mockClient()))
    await screen.findAllByRole('listitem')
    const row = rowOf(IDEMPOTENCY)
    const select = row.getByRole('combobox', { name: /Classification of/ })
    const options = within(select).getAllByRole('option').map((o) => o.textContent)
    expect(options).toEqual(['Choose classification', 'task', 'problem', 'decision', 'learning-topic', 'note', 'project', 'ticket', 'architecture-idea', 'question', 'thought'])
    expect(row.getByRole('button', { name: 'Choose a classification' })).toBeDisabled()
    expect(row.getByRole('button', { name: 'Dismiss' })).toBeEnabled()
  })

  it.each([
    ['task', 'Create task'],
    ['problem', 'Create task'],
    ['decision', 'Create decision'],
    ['learning-topic', 'Create lesson'],
    ['note', 'Create lesson'],
    ['project', 'Create project note'],
    ['question', 'Keep in inbox'],
  ])('the action label for %s is "%s"', async (kind, label) => {
    const user = userEvent.setup()
    open(withBodies(mockClient()))
    await screen.findAllByRole('listitem')
    const row = rowOf(IDEMPOTENCY)
    await user.selectOptions(row.getByRole('combobox'), kind)
    expect(row.getByRole('button', { name: label })).toBeEnabled()
    if (label === 'Keep in inbox') expect(row.queryByLabelText(/Title of the new note/)).not.toBeInTheDocument()
    else expect(row.getByLabelText(/Title of the new note/)).toBeInTheDocument()
  })

  it('shows the classification /triage wrote as a chip, not a select, and none on unclassified captures', async () => {
    open(mockClient())
    await screen.findAllByRole('listitem')
    const row = rowOf(TLS)
    expect(row.queryByRole('combobox')).not.toBeInTheDocument()
    expect(row.getByText('task')).toBeInTheDocument()
    expect(row.getByRole('button', { name: 'Create task' })).toBeInTheDocument()
    expect(rowOf(IDEMPOTENCY).getByRole('combobox')).toBeInTheDocument()
    expect(rowOf('decided to keep the OTP').getByText('decision')).toBeInTheDocument()
  })
})

describe('InboxPage: converting', () => {
  it('sends expected_hash, the classification and the optional title, then lists it as handled with the file written', async () => {
    const user = userEvent.setup()
    const client = withBodies(mockClient())
    const calls = spyTriage(client)
    open(client)
    await screen.findAllByRole('listitem')
    const before = (await client.lookupNote({ path: (await client.listNotes({ type: 'capture' })).results.find((n) => n.title.includes('Idempotency'))!.path })).content_hash
    const row = rowOf(IDEMPOTENCY)
    await user.selectOptions(row.getByRole('combobox'), 'decision')
    await user.type(row.getByLabelText(/Title of the new note/), 'Use idempotency keys')
    await user.click(row.getByRole('button', { name: 'Create decision' }))
    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0]).toMatchObject({ action: 'decision', classification: 'decision', title: 'Use idempotency keys', expected_hash: before })
    expect(calls[0].existing_target).toBeUndefined()
    const handled = await screen.findByRole('heading', { name: 'Handled this session' })
    const list = within(handled.closest('section')!)
    expect(list.getByText(/Wrote 05-Knowledge\/Decisions\/Use idempotency keys\.md/)).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('listitem', { name: IDEMPOTENCY })).not.toBeInTheDocument())
  })

  it('omits the title when left blank', async () => {
    const user = userEvent.setup()
    const client = withBodies(mockClient())
    const calls = spyTriage(client)
    open(client)
    await screen.findAllByRole('listitem')
    const row = rowOf(TLS)
    await user.click(row.getByRole('button', { name: 'Create task' }))
    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0].title).toBeUndefined()
  })

  it('a plain 409 reloads with the changed-in-Obsidian toast', async () => {
    const user = userEvent.setup()
    const client = withBodies(mockClient())
    client.triageCapture = async () => {
      throw new ApiError(409, 'stale')
    }
    open(client)
    await screen.findAllByRole('listitem')
    const row = rowOf(TLS)
    await user.click(row.getByRole('button', { name: 'Create task' }))
    expect((await screen.findAllByText(/changed in Obsidian, reloaded/)).length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
  })

  it('a partial failure offers Retry, which sends existing_target', async () => {
    const user = userEvent.setup()
    const client = withBodies(mockClient())
    const calls: TriageRequest[] = []
    const real = client.triageCapture.bind(client)
    client.triageCapture = async (input) => {
      calls.push(input)
      if (calls.length === 1) throw new ApiError(409, 'capture changed', { created_target: '02-Work/Tasks/Renew.md' })
      return real({ ...input, existing_target: undefined, title: 'Renew' })
    }
    open(client)
    await screen.findAllByRole('listitem')
    const row = rowOf(TLS)
    await user.click(row.getByRole('button', { name: 'Create task' }))
    expect(await row.findByRole('alert')).toHaveTextContent('Created 02-Work/Tasks/Renew.md')
    await user.click(row.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(calls).toHaveLength(2))
    expect(calls[0].existing_target).toBeUndefined()
    expect(calls[1]).toMatchObject({ action: 'task', existing_target: '02-Work/Tasks/Renew.md' })
    await waitFor(() => expect(row.queryByRole('alert')).not.toBeInTheDocument())
  })
})

describe('InboxPage: keep and dismiss', () => {
  it('keep writes the classification, keeps the row and then offers only Dismiss', async () => {
    const user = userEvent.setup()
    const client = withBodies(mockClient())
    const calls = spyTriage(client)
    open(client)
    await screen.findAllByRole('listitem')
    const row = rowOf('Should the standup list')
    await user.selectOptions(row.getByRole('combobox'), 'question')
    await user.click(row.getByRole('button', { name: 'Keep in inbox' }))
    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0]).toMatchObject({ action: 'keep', classification: 'question' })
    expect(await row.findByText(/Kept in inbox until its phase exists/)).toBeInTheDocument()
    expect(row.getAllByRole('button').map((b) => b.textContent)).not.toContain('Keep in inbox')
    expect(row.queryByRole('combobox')).not.toBeInTheDocument()
    expect(row.getByRole('button', { name: 'Dismiss' })).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(4)
    expect((await client.lookupNote({ path: calls[0].path })).frontmatter.classification).toBe('question')
  })

  it('a capture /triage classified with no target is shown as kept with only Dismiss', async () => {
    open(withBodies(mockClient(), { 'Should the standup': 'thought' }))
    await screen.findAllByRole('listitem')
    const row = rowOf('Should the standup list')
    expect(row.getByText('thought')).toBeInTheDocument()
    expect(row.getByRole('button', { name: 'Dismiss' })).toBeInTheDocument()
    expect(row.queryByRole('button', { name: /Create|Keep/ })).not.toBeInTheDocument()
  })

  it('dismiss sends the classification only when one is written', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    const calls = spyTriage(client)
    open(client)
    await screen.findAllByRole('listitem')
    await user.click(rowOf(TLS).getByRole('button', { name: 'Dismiss' }))
    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0]).toMatchObject({ action: 'dismiss', classification: 'task' })
  })

  it('dismiss sets status dismissed, sends the hash and lists it as handled', async () => {
    const user = userEvent.setup()
    const client = withBodies(mockClient())
    const calls = spyTriage(client)
    open(client)
    await screen.findAllByRole('listitem')
    await user.click(rowOf('Should the standup list').getByRole('button', { name: 'Dismiss' }))
    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0].action).toBe('dismiss')
    expect(calls[0].classification).toBeUndefined()
    expect(calls[0].expected_hash).toMatch(/^sha256:/)
    await waitFor(() => expect(screen.getAllByRole('listitem').length).toBeGreaterThan(0))
    const handled = await screen.findByRole('heading', { name: 'Handled this session' })
    expect(within(handled.closest('section')!).getByText(/Set status: dismissed in 00-Inbox\//)).toBeInTheDocument()
    expect((await client.listNotes({ type: 'capture', status: ['inbox'] })).results).toHaveLength(3)
  })
})

describe('InboxPage: keyboard and reader', () => {
  it('arrow keys move between rows and Enter moves into the row actions', async () => {
    const user = userEvent.setup()
    open(withBodies(mockClient()))
    const rows = await screen.findAllByRole('listitem')
    rows[0].focus()
    await user.keyboard('{ArrowDown}')
    expect(rows[1]).toHaveFocus()
    await user.keyboard('{ArrowUp}')
    expect(rows[0]).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(within(rows[0]).getByRole('combobox')).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(rows[0]).toHaveFocus()
  })

  it('selecting a row opens the note reader beside the list at wide widths', async () => {
    const user = userEvent.setup()
    const { router } = open(withBodies(mockClient()))
    await screen.findAllByRole('listitem')
    await user.click(rowOf(TLS).getByRole('button', { name: /^Open/ }))
    expect(new URLSearchParams(router.state.location.search).get('note')).toMatch(/^00-Inbox\//)
    expect(await screen.findByRole('complementary', { name: 'Open note' })).toBeInTheDocument()
  })

  it('selecting a row below the split width goes to the note route', async () => {
    const user = userEvent.setup()
    const { router } = open(withBodies(mockClient()), 600)
    await screen.findAllByRole('listitem')
    await user.click(rowOf(TLS).getByRole('button', { name: /^Open/ }))
    expect(router.state.location.pathname).toBe('/notes')
  })
})

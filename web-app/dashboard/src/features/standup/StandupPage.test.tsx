import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiError, type ApiClient } from '@/api/client'
import type { NoteDetail } from '@/api/types'
import { STANDUP_SECTIONS } from '@/api/types'
import { mockClient, renderInApp, TODAY } from '@/test/helpers'
import { StandupPage } from './StandupPage'

const section = (name: string) => screen.getByRole('region', { name })
const tile = (label: string) => screen.getAllByText(label).map((e) => e.closest('a')).find((a) => a?.className.includes('h-16'))!

describe('StandupPage, missing note', () => {
  it('shows the carry-forward preview first, then creates the note on Start standup', async () => {
    const client = mockClient({ standup: 'missing' })
    const start = vi.spyOn(client, 'startStandup')
    renderInApp(<StandupPage />, client)

    expect(await screen.findByText('Not started')).toBeInTheDocument()
    // The preview comes from getStandupToday and nothing has been written.
    expect(within(section('Today')).getByText('Investigate missing OTP email')).toBeInTheDocument()
    expect(within(section('Blockers')).getByText(/Confirm rate limit/)).toBeInTheDocument()
    expect(start).not.toHaveBeenCalled()
    expect(screen.queryByRole('textbox', { name: /Add a line to/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Fill with carry-forward' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Start standup' }))
    expect(start).toHaveBeenCalledTimes(1)
    expect(await screen.findByText(`Created 01-Daily/2026/${TODAY}.md with carry-forward`)).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Start standup' })).not.toBeInTheDocument())
    expect(screen.getByText('Edited by hand')).toBeInTheDocument()
    expect(screen.getAllByRole('textbox', { name: /Add a line to/ })).toHaveLength(6)
  })

  it('links task lines through the note reader and project lines through the project route', async () => {
    renderInApp(<StandupPage />, mockClient({ standup: 'missing' }))
    const task = await within(await screen.findByRole('region', { name: 'Today' })).findByRole('link', { name: 'Investigate missing OTP email' })
    expect(task.getAttribute('href')).toBe(`/notes?path=${encodeURIComponent('02-Work/Tasks/Investigate missing OTP email.md')}`)
    const project = await within(section('Related Tasks / Projects')).findByRole('link', { name: 'LoadUp' })
    expect(project).toHaveAttribute('href', '/projects/loadup')
  })
})

describe('StandupPage, untouched note', () => {
  it('offers Fill with carry-forward and not Start standup', async () => {
    const client = mockClient({ standup: 'untouched' })
    const start = vi.spyOn(client, 'startStandup')
    renderInApp(<StandupPage />, client)

    expect(await screen.findByText('Untouched')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Start standup' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Fill with carry-forward' }))
    expect(start).toHaveBeenCalledTimes(1)
    expect(await screen.findByText(`Filled 01-Daily/2026/${TODAY}.md with carry-forward`)).toBeInTheDocument()
    expect(await within(section('Today')).findByText('Investigate missing OTP email')).toBeInTheDocument()
  })
})

describe('StandupPage, note edited by hand', () => {
  it('shows the note as written with no start or fill', async () => {
    renderInApp(<StandupPage />, mockClient({ standup: 'touched' }))
    expect(await within(await screen.findByRole('region', { name: 'Today' })).findByText('Pair with QA on the OTP reproduction')).toBeInTheDocument()
    expect(screen.getByText('Edited by hand')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Start standup' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Fill with carry-forward' })).not.toBeInTheDocument()
    // Nothing carry-forward would add is shown.
    expect(within(section('Today')).queryByText('Investigate missing OTP email')).not.toBeInTheDocument()
  })

  it('renders the six sections in the vault heading order', async () => {
    renderInApp(<StandupPage />, mockClient({ standup: 'touched' }))
    await screen.findByRole('region', { name: 'Today' })
    const names = screen.getAllByRole('region').map((r) => r.getAttribute('aria-label'))
    expect(names).toEqual([...STANDUP_SECTIONS])
  })

  it('counts the four tiles from the lines on screen', async () => {
    renderInApp(<StandupPage />, mockClient({ standup: 'touched' }))
    await screen.findByRole('region', { name: 'Today' })
    await waitFor(() => expect(tile('Planned today')).toHaveTextContent('1'))
    expect(tile('Carried over')).toHaveTextContent('0')
    expect(tile('Blockers')).toHaveTextContent('0')
    expect(tile('Open follow-ups')).toHaveTextContent('0')
  })

  it('shows the standup as plain text in a read-only textarea without touching the clipboard', async () => {
    const writeText = vi.fn()
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    renderInApp(<StandupPage />, mockClient({ standup: 'touched' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Copy as text' }))
    const box = screen.getByRole('textbox', { name: /Ready to paste/ })
    expect(box).toHaveAttribute('readonly')
    expect((box as HTMLTextAreaElement).value).toContain('Standup, Tuesday 6 October')
    expect((box as HTMLTextAreaElement).value).toContain('- Pair with QA on the OTP reproduction')
    expect(writeText).not.toHaveBeenCalled()
  })

  it('shows Yesterday as a read-only view of the previous note, labelled with its date', async () => {
    renderInApp(<StandupPage />, mockClient({ standup: 'touched' }))
    await screen.findByRole('region', { name: 'Done' })
    expect(await within(section('Done')).findByText('Yesterday, Oct 5')).toBeInTheDocument()
    expect(within(section('Done')).getByText(/Read-only view of Done in/)).toBeInTheDocument()
  })

  it('marks ticket and meeting lines as preview', async () => {
    renderInApp(<StandupPage />, mockClient({ standup: 'touched' }))
    const related = await screen.findByRole('region', { name: 'Related Tasks / Projects' })
    expect(within(related).getByText('LD-482')).toBeInTheDocument()
    expect(within(related).getByText('Preview')).toBeInTheDocument()
  })
})

describe('StandupPage, adding a line', () => {
  it('appends to the chosen section with the note hash, then shows the line', async () => {
    const client = mockClient({ standup: 'touched' })
    const append = vi.spyOn(client, 'appendToStandup')
    renderInApp(<StandupPage />, client)

    const blockers = await screen.findByRole('region', { name: 'Blockers' })
    await userEvent.type(within(blockers).getByRole('textbox', { name: 'Add a line to Blockers' }), 'Waiting on the staging refresh')
    await userEvent.click(within(blockers).getByRole('button', { name: 'Add' }))

    expect(append).toHaveBeenCalledTimes(1)
    expect(append).toHaveBeenCalledWith({ section: 'Blockers', text: 'Waiting on the staging refresh', expected_hash: 'sha256:mock-standup-0' })
    expect(await screen.findByText(`Added to ## Blockers in 01-Daily/2026/${TODAY}.md`)).toBeInTheDocument()
    expect(await within(section('Blockers')).findByText('Waiting on the staging refresh')).toBeInTheDocument()
    expect(within(section('Blockers')).getByRole('textbox', { name: 'Add a line to Blockers' })).toHaveValue('')
  })

  it('sends only the entry text, and the list shows the marker the writer adds', async () => {
    const client = mockClient({ standup: 'touched' })
    const append = vi.spyOn(client, 'appendToStandup')
    renderInApp(<StandupPage />, client)
    const today = await screen.findByRole('region', { name: 'Today' })
    await userEvent.type(within(today).getByRole('textbox', { name: 'Add a line to Today' }), 'Review the PR{Enter}')
    expect(append).toHaveBeenCalledWith(expect.objectContaining({ section: 'Today', text: 'Review the PR' }))
    expect(await within(section('Today')).findByRole('img', { name: 'Not done' })).toBeInTheDocument()
  })

  it('does not add an empty line', async () => {
    renderInApp(<StandupPage />, mockClient({ standup: 'touched' }))
    const today = await screen.findByRole('region', { name: 'Today' })
    expect(within(today).getByRole('button', { name: 'Add' })).toBeDisabled()
  })

  it('on a 409 reloads, tells the user, and keeps what they typed', async () => {
    const client = mockClient({ standup: 'touched' })
    vi.spyOn(client, 'appendToStandup').mockRejectedValue(new ApiError(409, 'changed'))
    const get = vi.spyOn(client, 'getStandupToday')
    renderInApp(<StandupPage />, client)

    const today = await screen.findByRole('region', { name: 'Today' })
    const input = within(today).getByRole('textbox', { name: 'Add a line to Today' })
    await userEvent.type(input, 'Keep me')
    const callsBefore = get.mock.calls.length
    await userEvent.click(within(today).getByRole('button', { name: 'Add' }))

    expect(await screen.findByText(/changed in Obsidian, reloaded/)).toBeInTheDocument()
    expect(input).toHaveValue('Keep me')
    await waitFor(() => expect(get.mock.calls.length).toBeGreaterThan(callsBefore))
  })

  it('shows the message of any other failure', async () => {
    const client = mockClient({ standup: 'touched' })
    vi.spyOn(client, 'appendToStandup').mockRejectedValue(new ApiError(422, 'Nothing to append.'))
    renderInApp(<StandupPage />, client)
    const today = await screen.findByRole('region', { name: 'Today' })
    await userEvent.type(within(today).getByRole('textbox', { name: 'Add a line to Today' }), 'x')
    await userEvent.click(within(today).getByRole('button', { name: 'Add' }))
    expect(await screen.findByText('Nothing to append.')).toBeInTheDocument()
  })
})

describe('StandupPage, adding to an untouched note', () => {
  it('fills the note with carry-forward first, then appends with the filled note hash', async () => {
    const client = mockClient({ standup: 'untouched' })
    const start = vi.spyOn(client, 'startStandup')
    const append = vi.spyOn(client, 'appendToStandup')
    renderInApp(<StandupPage />, client)

    const followUps = await screen.findByRole('region', { name: 'Follow-ups' })
    await userEvent.type(within(followUps).getByRole('textbox', { name: 'Add a line to Follow-ups' }), 'Ask infra for the refresh date')
    await userEvent.click(within(followUps).getByRole('button', { name: 'Add' }))

    expect(await screen.findByText(`Filled 01-Daily/2026/${TODAY}.md with carry-forward, then appended "Ask infra for the refresh date" under Follow-ups`)).toBeInTheDocument()
    expect(start).toHaveBeenCalledTimes(1)
    // The fill bumped the hash (r0 to r1); the append carries the new one, not the hash the page loaded.
    expect(append).toHaveBeenCalledWith({ section: 'Follow-ups', text: 'Ask infra for the refresh date', expected_hash: 'sha256:mock-standup-1' })
    expect(await within(section('Today')).findByText('Investigate missing OTP email')).toBeInTheDocument()
    expect(await within(section('Follow-ups')).findByText('Ask infra for the refresh date')).toBeInTheDocument()
  })

  it('does not fill a note that is already edited', async () => {
    const client = mockClient({ standup: 'touched' })
    const start = vi.spyOn(client, 'startStandup')
    renderInApp(<StandupPage />, client)
    const today = await screen.findByRole('region', { name: 'Today' })
    await userEvent.type(within(today).getByRole('textbox', { name: 'Add a line to Today' }), 'x{Enter}')
    await screen.findByText(/Added to ## Today/)
    expect(start).not.toHaveBeenCalled()
  })
})

describe('StandupPage, wikilinks use the API resolution', () => {
  const note = (base: NoteDetail): NoteDetail => ({
    ...base,
    body: noteBody({
      Today: ['- [ ] [[Fix N+1]]', '- [ ] [[Ghost task]]', '- [ ] [[LoadUp]]', '- [ ] [[Rotate staging API credentials]]'],
    }),
    links: {
      'Fix N+1': { path: null, state: 'ambiguous' },
      'Ghost task': { path: null, state: 'unresolved' },
      LoadUp: { path: '05-Knowledge/Lessons/LoadUp.md', state: 'resolved' },
      'Rotate staging API credentials': { path: '02-Work/Tasks/Rotate staging API credentials.md', state: 'resolved' },
    },
  })

  it('shows ambiguous and unresolved targets as text with the word, and never lets a project title override the server', async () => {
    const base = mockClient({ standup: 'touched' })
    const current = await base.getStandupToday()
    if (!current.exists) throw new Error('expected a note')
    const client: ApiClient = { ...base, getStandupToday: async () => ({ ...current, note: note(current.note) }) }
    renderInApp(<StandupPage />, client)

    const today = await screen.findByRole('region', { name: 'Today' })
    await within(today).findByText(/Fix N\+1/)
    expect(within(today).queryByRole('link', { name: 'Fix N+1' })).not.toBeInTheDocument()
    expect(within(today).getByText('(ambiguous)')).toBeInTheDocument()
    expect(within(today).queryByRole('link', { name: 'Ghost task' })).not.toBeInTheDocument()
    expect(within(today).getByText('(unresolved)')).toBeInTheDocument()
    // The server resolved "LoadUp" to a lesson, so it is a note link even though a project has that title.
    expect(within(today).getByRole('link', { name: 'LoadUp' })).toHaveAttribute('href', `/notes?path=${encodeURIComponent('05-Knowledge/Lessons/LoadUp.md')}`)
    expect(within(today).getByRole('link', { name: 'Rotate staging API credentials' })).toHaveAttribute('href', expect.stringContaining('/notes?path='))
  })
})

describe('StandupPage, history', () => {
  it('lists daily notes newest first, asking the API for them newest first', async () => {
    const client = mockClient({ standup: 'touched' })
    const list = vi.spyOn(client, 'listNotes')
    renderInApp(<StandupPage />, client)
    const card = (await screen.findByRole('heading', { name: 'Past standups' })).closest('section')!
    await within(card).findByText('2026-10-05')
    const dates = within(card).getAllByRole('button').map((b) => b.textContent!.slice(0, 10))
    expect(dates).toEqual(['2026-10-06', '2026-10-05', '2026-10-02', '2026-10-01'])
    expect(list).toHaveBeenCalledWith(expect.objectContaining({ type: 'daily', ordering: '-path' }))
  })

  it('opens a past note read-only and goes back to today', async () => {
    renderInApp(<StandupPage />, mockClient({ standup: 'touched' }))
    const card = (await screen.findByRole('heading', { name: 'Past standups' })).closest('section')!
    await userEvent.click(await within(card).findByRole('button', { name: /Monday 5 October/ }))

    expect(await screen.findByText('Read-only, past note')).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: /Add a line to/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Start standup' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Back to today' }))
    expect(await screen.findByText('Edited by hand')).toBeInTheDocument()
  })

  it('says what to do when there are no earlier notes', async () => {
    const base = mockClient({ standup: 'missing' })
    const client: ApiClient = { ...base, listNotes: async () => ({ count: 0, next: null, previous: null, results: [] }) }
    renderInApp(<StandupPage />, client)
    expect(await screen.findByText(/No earlier daily notes yet/)).toBeInTheDocument()
  })
})

describe('StandupPage, states', () => {
  it('announces loading', () => {
    renderInApp(<StandupPage />, mockClient({ delayMs: 50 }))
    expect(screen.getAllByText('Loading').length).toBeGreaterThan(0)
  })

  it('shows an error with a retry when today cannot be read', async () => {
    const client = mockClient()
    vi.spyOn(client, 'getStandupToday').mockRejectedValue(new Error('Network down'))
    renderInApp(<StandupPage />, client)
    const alerts = await screen.findAllByRole('alert')
    expect(alerts[0]).toHaveTextContent('Network down')
    expect(within(alerts[0]).getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})

// ---- patterns ---------------------------------------------------------------

const noteBody = (parts: Partial<Record<(typeof STANDUP_SECTIONS)[number], string[]>>) =>
  `# Standup\n\n${STANDUP_SECTIONS.map((h) => `## ${h}\n\n${(parts[h] ?? []).join('\n')}\n`).join('\n')}`

/** A client whose daily notes are the given bodies, newest first by date. */
function clientWithDailies(bodies: Record<string, string>): ApiClient {
  const base = mockClient({ standup: 'missing' })
  const summary = (date: string) => ({ id: null, path: `01-Daily/2026/${date}.md`, type: 'daily' as const, title: date, status: null, priority: null, project: null, due: null, blocked_by: null, decided: null, tags: [], created: date, modified: `${date}T17:00:00+08:00`, parse_error: null })
  const dates = Object.keys(bodies).sort().reverse()
  return {
    ...base,
    listNotes: async (params) => {
      if (params?.type !== 'daily') return base.listNotes(params)
      return { count: dates.length, next: null, previous: null, results: dates.map(summary) }
    },
    lookupNote: async (by) => {
      if (!('path' in by) || !by.path.startsWith('01-Daily/')) return base.lookupNote(by)
      const date = by.path.slice(-13, -3)
      return { ...summary(date), frontmatter: {}, body: bodies[date], content_hash: `sha256:${date}`, backlinks: [], links: {} } satisfies NoteDetail
    },
  }
}

describe('StandupPage, patterns', () => {
  const client = () =>
    clientWithDailies({
      '2026-10-05': noteBody({
        Done: ['- [x] [[Reproduce duplicate settlement rows]]', '- [x] [[Fix N+1 query on account listing]]'],
        Today: ['- [ ] [[Rotate staging API credentials]]'],
        Blockers: ['- [[Confirm rate limit with SMS provider]] (blocked by: provider account manager)'],
        'Follow-ups': ['- [ ] Ask QA for the UAT slot'],
      }),
      '2026-10-02': noteBody({
        Done: ['- [x] [[Reproduce duplicate settlement rows]]', '- [x] Tidy my desk'],
        Today: ['- [ ] [[Rotate staging API credentials]]'],
        Blockers: ['- [[Confirm rate limit with SMS provider]]'],
      }),
      '2026-10-01': noteBody({ Today: ['- [ ] [[Rotate staging API credentials]]'] }),
    })

  async function openPatterns() {
    renderInApp(<StandupPage />, client())
    await userEvent.click(await screen.findByRole('button', { name: 'Patterns' }))
  }

  it('lists carry-over items that were in Today for three days', async () => {
    await openPatterns()
    const card = (await screen.findByRole('heading', { name: 'What keeps rolling over?' })).closest('section')!
    expect(within(card).getByText(/Rotate staging API credentials/)).toBeInTheDocument()
    expect(within(card).getByText('3 days')).toBeInTheDocument()
    expect(within(card).getByText(/Since Oct 1/)).toBeInTheDocument()
  })

  it('lists recurring blockers with the count of days', async () => {
    await openPatterns()
    const card = (await screen.findByRole('heading', { name: 'Which blockers keep coming back?' })).closest('section')!
    expect(within(card).getByText('Confirm rate limit with SMS provider')).toBeInTheDocument()
    expect(within(card).getByText('2 days')).toBeInTheDocument()
    expect(within(card).getByText(/Blocked by: provider account manager/)).toBeInTheDocument()
  })

  it('counts Done work by project over the last five standups, as text beside rounded bars', async () => {
    await openPatterns()
    const card = (await screen.findByRole('heading', { name: 'Where did the work go?' })).closest('section')!
    const rows = await within(card).findAllByRole('listitem')
    // IPP: the settlement task twice. LoadUp: the N+1 task. No project: free text.
    expect(rows.map((r) => r.textContent)).toEqual(['IPP2', 'LoadUp1', 'No project1'])
    expect(within(card).getByRole('link', { name: 'IPP' })).toHaveAttribute('href', '/projects/ipp')
  })

  it('lists outstanding follow-ups with their age', async () => {
    await openPatterns()
    const card = (await screen.findByRole('heading', { name: 'Which follow-ups are still open?' })).closest('section')!
    expect(within(card).getByText('Ask QA for the UAT slot')).toBeInTheDocument()
    expect(within(card).getByText('1 day')).toBeInTheDocument()
  })

  it('says so when there is nothing to report', async () => {
    renderInApp(<StandupPage />, clientWithDailies({ '2026-10-05': noteBody({}) }))
    await userEvent.click(await screen.findByRole('button', { name: 'Patterns' }))
    expect(await screen.findByText('No blocker has been listed on more than one day.')).toBeInTheDocument()
    expect(screen.getByText('No unchecked follow-ups.')).toBeInTheDocument()
    expect(screen.getByText('Nothing has been listed under Done yet.')).toBeInTheDocument()
  })

  it('shows real values on the mock client daily notes', async () => {
    renderInApp(<StandupPage />, mockClient({ standup: 'missing' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Patterns' }))
    const carry = (await screen.findByRole('heading', { name: 'What keeps rolling over?' })).closest('section')!
    expect(await within(carry).findByText(/Investigate missing OTP email/)).toBeInTheDocument()
    const followUps = screen.getByRole('heading', { name: 'Which follow-ups are still open?' }).closest('section')!
    expect(within(followUps).getByText('Ask infra for the staging database refresh date')).toBeInTheDocument()
    const work = screen.getByRole('heading', { name: 'Where did the work go?' }).closest('section')!
    expect((await within(work).findAllByRole('listitem')).length).toBeGreaterThan(1)
  })
})

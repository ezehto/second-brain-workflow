import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useCallback, useEffect, useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { useApi } from '@/api/ApiProvider'
import { ApiError } from '@/api/client'
import { useQuery } from '@/api/useQuery'
import { mockClient, renderInApp } from '@/test/helpers'
import { StatusMenu } from './StatusMenu'

const TASK = '02-Work/Tasks/Rotate staging API credentials.md'

/** A note read from the API, so the menu's status follows refetches like a real page. */
function Harness({ path }: { path: string }) {
  const api = useApi()
  const list = useQuery(useCallback(() => api.listNotes({ page_size: 100 }), [api]))
  if (list.status !== 'success') return null
  return <StatusMenu note={list.data.results.find((n) => n.path === path)!} />
}

const control: { set: (status: string) => void } = { set: () => {} }

/** A note whose status the test moves from outside, as a refetch after an Obsidian edit would. */
function Controlled({ note }: { note: { path: string; type: string; title: string; status: string } }) {
  const [status, setStatus] = useState(note.status)
  useEffect(() => {
    control.set = setStatus
  }, [])
  return <StatusMenu note={{ ...note, status }} />
}

const trigger = (name: RegExp) => screen.findByRole('button', { name })

describe('StatusMenu', () => {
  it('changes status from the keyboard alone and shows the new status', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    renderInApp(<Harness path={TASK} />, client)
    const button = await trigger(/Status: planned/)
    button.focus()
    await user.keyboard('{Enter}')
    const items = await screen.findAllByRole('menuitemradio')
    expect(items.map((i) => i.textContent)).toEqual(['inbox', 'planned', 'in-progress', 'blocked', 'review', 'done', 'cancelled'])
    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}')
    expect(await screen.findByRole('status')).toHaveTextContent(`Set status: in-progress in ${TASK}`)
    expect(await trigger(/Status: in-progress/)).toBeInTheDocument()
    expect((await client.lookupNote({ path: TASK })).status).toBe('in-progress')
  })

  it('offers the vocabulary of the note\'s type', async () => {
    const user = userEvent.setup()
    renderInApp(<Harness path="05-Knowledge/Decisions/Use idempotency keys on payment callbacks.md" />)
    await user.click(await trigger(/Status: proposed/))
    const items = await screen.findAllByRole('menuitemradio')
    expect(items.map((i) => i.textContent)).toEqual(['proposed', 'accepted', 'superseded', 'rejected'])
  })

  it('shows the new status before the server answers, and drops it if the write fails', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    let reject: (e: Error) => void = () => {}
    client.changeStatus = () => new Promise((_, r) => (reject = r))
    renderInApp(<Harness path={TASK} />, client)
    await user.click(await trigger(/Status: planned/))
    await user.click(await screen.findByRole('menuitemradio', { name: 'review' }))
    expect(await trigger(/Status: review/)).toBeInTheDocument()
    reject(new ApiError(422, 'review is not allowed here'))
    expect(await screen.findByRole('status')).toHaveTextContent('review is not allowed here')
    expect(await trigger(/Status: planned/)).toBeInTheDocument()
  })

  it('on a 409 says the note changed in Obsidian, refetches, and shows the real status', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    const listNotes = vi.spyOn(client, 'listNotes')
    // The note really became "blocked" in Obsidian while the page showed "planned".
    const hash = (await client.lookupNote({ path: TASK })).content_hash
    await client.changeStatus({ path: TASK, status: 'blocked', expected_hash: hash })
    const stale = client.listNotes
    let first = true
    client.listNotes = async (p) => {
      const page = await stale(p)
      if (first) {
        first = false
        return { ...page, results: page.results.map((n) => (n.path === TASK ? { ...n, status: 'planned' } : n)) }
      }
      return page
    }
    client.lookupNote = async () => ({ ...(await mockClient().lookupNote({ path: TASK })), content_hash: 'sha256:stale' })
    renderInApp(<Harness path={TASK} />, client)
    await user.click(await trigger(/Status: planned/))
    await user.click(await screen.findByRole('menuitemradio', { name: 'review' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Rotate staging API credentials changed in Obsidian, reloaded.')
    expect(listNotes).toHaveBeenCalled()
    expect(await trigger(/Status: blocked/)).toBeInTheDocument()
  })

  it('asks for evidence before a task becomes done, and writes it under Notes', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    renderInApp(<Harness path={TASK} />, client)
    await user.click(await trigger(/Status: planned/))
    await user.click(await screen.findByRole('menuitemradio', { name: 'done' }))
    const dialog = await screen.findByRole('dialog', { name: 'Mark as done' })
    expect((await client.lookupNote({ path: TASK })).status).toBe('planned')
    await user.type(within(dialog).getByLabelText(/Evidence/), 'Rotated and verified')
    await user.click(within(dialog).getByRole('button', { name: 'Mark done' }))
    await waitFor(async () => expect((await client.lookupNote({ path: TASK })).status).toBe('done'))
    expect((await client.lookupNote({ path: TASK })).body).toContain('- Rotated and verified')
    expect(await trigger(/Status: done/)).toBeInTheDocument()
  })

  it('leaves the status alone when the evidence prompt is cancelled', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    const change = vi.spyOn(client, 'changeStatus')
    renderInApp(<Harness path={TASK} />, client)
    await user.click(await trigger(/Status: planned/))
    await user.click(await screen.findByRole('menuitemradio', { name: 'done' }))
    await user.click(await screen.findByRole('button', { name: 'Cancel' }))
    expect(change).not.toHaveBeenCalled()
    expect(await trigger(/Status: planned/)).toBeInTheDocument()
  })

  it('does not ask for evidence for other statuses or other types', async () => {
    const user = userEvent.setup()
    renderInApp(<Harness path={TASK} />)
    await user.click(await trigger(/Status: planned/))
    await user.click(await screen.findByRole('menuitemradio', { name: 'cancelled' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('is a plain chip for a note type with no status vocabulary', async () => {
    renderInApp(<StatusMenu note={{ path: 'a.md', type: 'daily', title: 'a', status: null }} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByText('N/A')).toBeInTheDocument()
  })

  describe('after review findings', () => {
    it('shows the vault status when the note goes back to its original status, and a new choice works', async () => {
      const user = userEvent.setup()
      const client = mockClient()
      const note = { path: TASK, type: 'task', title: 'Rotate staging API credentials', status: 'planned' }
      renderInApp(<Controlled note={note} />, client)
      await user.click(await trigger(/Status: planned/))
      await user.click(await screen.findByRole('menuitemradio', { name: 'review' }))
      expect(await trigger(/Status: review/)).toBeInTheDocument()
      // The list refetched and showed review ...
      act(() => control.set('review'))
      expect(await trigger(/Status: review/)).toBeInTheDocument()
      // ... then Obsidian put it back to planned.
      act(() => control.set('planned'))
      expect(await trigger(/Status: planned/)).toBeInTheDocument()
      // A new choice of the old optimistic value is not swallowed.
      await user.click(await trigger(/Status: planned/))
      await user.click(await screen.findByRole('menuitemradio', { name: 'review' }))
      expect(await screen.findAllByRole('status')).not.toHaveLength(0)
      await waitFor(async () => expect((await client.lookupNote({ path: TASK })).status).toBe('review'))
    })

    it('returns focus to the trigger after a normal change', async () => {
      const user = userEvent.setup()
      renderInApp(<Harness path={TASK} />)
      const button = await trigger(/Status: planned/)
      await user.click(button)
      await user.click(await screen.findByRole('menuitemradio', { name: 'review' }))
      const after = await trigger(/Status: review/)
      await waitFor(() => expect(after).toHaveFocus())
    })

    it.each([
      ['Cancel', async (user: ReturnType<typeof userEvent.setup>) => user.click(await screen.findByRole('button', { name: 'Cancel' }))],
      ['Escape', async (user: ReturnType<typeof userEvent.setup>) => user.keyboard('{Escape}')],
    ])('returns focus to the trigger after %s on the evidence dialog', async (_name, dismiss) => {
      const user = userEvent.setup()
      renderInApp(<Harness path={TASK} />)
      await user.click(await trigger(/Status: planned/))
      await user.click(await screen.findByRole('menuitemradio', { name: 'done' }))
      await screen.findByRole('dialog', { name: 'Mark as done' })
      await dismiss(user)
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(await trigger(/Status: planned/)).toHaveFocus()
    })

    it('takes the 409 branch on a list page when the fresh status differs from the one shown, without writing', async () => {
      const user = userEvent.setup()
      const client = mockClient()
      const change = vi.spyOn(client, 'changeStatus')
      const note = { path: TASK, type: 'task', title: 'Rotate staging API credentials', status: 'planned' }
      // Obsidian moved it to blocked; the list (and so the prop) still says planned.
      const hash = (await client.lookupNote({ path: TASK })).content_hash
      await client.changeStatus({ path: TASK, status: 'blocked', expected_hash: hash })
      change.mockClear()
      renderInApp(<StatusMenu note={note} />, client)
      await user.click(await trigger(/Status: planned/))
      await user.click(await screen.findByRole('menuitemradio', { name: 'review' }))
      expect(await screen.findByRole('status')).toHaveTextContent('Rotate staging API credentials changed in Obsidian, reloaded.')
      expect(change).not.toHaveBeenCalled()
      expect((await client.lookupNote({ path: TASK })).status).toBe('blocked')
      expect(await trigger(/Status: planned/)).toBeInTheDocument()
    })

    it('does not raise a 409 on a second quick change from a list page', async () => {
      const user = userEvent.setup()
      const client = mockClient()
      renderInApp(<Harness path={TASK} />, client)
      await user.click(await trigger(/Status: planned/))
      await user.click(await screen.findByRole('menuitemradio', { name: 'review' }))
      await screen.findByText(`Set status: review in ${TASK}`)
      await user.click(await trigger(/Status: review/))
      await user.click(await screen.findByRole('menuitemradio', { name: 'blocked' }))
      await waitFor(async () => expect((await client.lookupNote({ path: TASK })).status).toBe('blocked'))
      expect(screen.queryByText(/changed in Obsidian/)).not.toBeInTheDocument()
    })

    it('uses the given contentHash, and the returned hash for a second change until the prop catches up', async () => {
      const user = userEvent.setup()
      const client = mockClient()
      const detail = await client.lookupNote({ path: TASK })
      const lookup = vi.spyOn(client, 'lookupNote')
      const change = vi.spyOn(client, 'changeStatus')
      const note = { path: TASK, type: 'task', title: detail.title, status: 'planned' }
      renderInApp(<StatusMenu note={note} contentHash={detail.content_hash} />, client)
      await user.click(await trigger(/Status: planned/))
      await user.click(await screen.findByRole('menuitemradio', { name: 'review' }))
      await waitFor(() => expect(change).toHaveBeenCalledTimes(1))
      expect(change.mock.calls[0][0].expected_hash).toBe(detail.content_hash)
      await screen.findByText(`Set status: review in ${TASK}`)
      await user.click(await trigger(/Status: review/))
      await user.click(await screen.findByRole('menuitemradio', { name: 'blocked' }))
      await waitFor(() => expect(change).toHaveBeenCalledTimes(2))
      expect(change.mock.calls[1][0].expected_hash).not.toBe(detail.content_hash)
      expect(lookup).not.toHaveBeenCalled()
      expect(screen.queryByText(/changed in Obsidian/)).not.toBeInTheDocument()
    })

    it('reports a stale contentHash as a 409 and writes nothing', async () => {
      const user = userEvent.setup()
      const client = mockClient()
      const note = { path: TASK, type: 'task', title: 'Rotate staging API credentials', status: 'planned' }
      renderInApp(<StatusMenu note={note} contentHash="sha256:stale" />, client)
      await user.click(await trigger(/Status: planned/))
      await user.click(await screen.findByRole('menuitemradio', { name: 'review' }))
      expect(await screen.findByRole('status')).toHaveTextContent('changed in Obsidian, reloaded.')
      expect((await client.lookupNote({ path: TASK })).status).toBe('planned')
    })

    it('on a 404 says the note moved or was deleted, and refetches', async () => {
      const user = userEvent.setup()
      const client = mockClient()
      const note = { path: TASK, type: 'task', title: 'Rotate staging API credentials', status: 'planned' }
      client.lookupNote = async () => {
        throw new ApiError(404, 'Not found')
      }
      renderInApp(<StatusMenu note={note} />, client)
      await user.click(await trigger(/Status: planned/))
      await user.click(await screen.findByRole('menuitemradio', { name: 'review' }))
      expect(await screen.findByRole('status')).toHaveTextContent('Note moved or deleted in Obsidian, reloaded.')
      expect(await trigger(/Status: planned/)).toBeInTheDocument()
    })

    it('keeps the typed evidence when the done write fails, and clears it after a success', async () => {
      const user = userEvent.setup()
      const client = mockClient()
      const real = client.changeStatus
      let fail = true
      client.changeStatus = async (input) => {
        if (fail) throw new ApiError(500, 'Server error')
        return real(input)
      }
      renderInApp(<Harness path={TASK} />, client)
      await user.click(await trigger(/Status: planned/))
      await user.click(await screen.findByRole('menuitemradio', { name: 'done' }))
      await user.type(await screen.findByLabelText(/Evidence/), 'Rotated and verified')
      await user.click(screen.getByRole('button', { name: 'Mark done' }))
      expect(await screen.findByRole('status')).toHaveTextContent('Server error')
      await user.click(await trigger(/Status: planned/))
      await user.click(await screen.findByRole('menuitemradio', { name: 'done' }))
      expect(await screen.findByLabelText(/Evidence/)).toHaveValue('Rotated and verified')
      fail = false
      await user.click(screen.getByRole('button', { name: 'Mark done' }))
      await waitFor(async () => expect((await client.lookupNote({ path: TASK })).status).toBe('done'))
      await user.click(await trigger(/Status: done/))
      await user.click(await screen.findByRole('menuitemradio', { name: 'planned' }))
      await user.click(await trigger(/Status: planned/))
      await user.click(await screen.findByRole('menuitemradio', { name: 'done' }))
      expect(await screen.findByLabelText(/Evidence/)).toHaveValue('')
    })
  })
})

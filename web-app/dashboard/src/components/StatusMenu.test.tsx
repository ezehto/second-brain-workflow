import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useCallback } from 'react'
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
})

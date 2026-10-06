import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ApiError } from '@/api/client'
import { useCallback } from 'react'
import { useApi } from '@/api/ApiProvider'
import { useQuery } from '@/api/useQuery'
import { mockClient, renderInApp } from '@/test/helpers'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { NewMenu, QuickActionsProvider } from './QuickActions'

const Harness = () => (
  <QuickActionsProvider>
    <NewMenu />
  </QuickActionsProvider>
)

/** Opens one creation dialog the way a person does: the New menu, then the item. */
async function openAction(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(screen.getByRole('button', { name: 'New' }))
  await user.click(await screen.findByRole('menuitem', { name }))
}

describe('QuickActions', () => {
  it('has the five actions in the New menu, each with its shortcut', async () => {
    const user = userEvent.setup()
    renderInApp(<Harness />)
    await user.click(screen.getByRole('button', { name: 'New' }))
    const items = await screen.findAllByRole('menuitem')
    expect(items.map((i) => i.textContent)).toEqual(['TaskT', 'Follow-upF', 'DecisionD', 'NoteN', 'CaptureC'])
  })

  it('opens a dialog from its single-key shortcut, but not while typing', async () => {
    const user = userEvent.setup()
    renderInApp(
      <>
        <input aria-label="elsewhere" />
        <Harness />
      </>,
    )
    await user.click(screen.getByLabelText('elsewhere'))
    await user.keyboard('t')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(document.body)
    await user.keyboard('c')
    expect(await screen.findByRole('dialog', { name: 'Capture' })).toBeInTheDocument()
  })

  it('captures a thought and names the file in a toast', async () => {
    const user = userEvent.setup()
    renderInApp(<Harness />)
    await openAction(user, 'Capture')
    const dialog = screen.getByRole('dialog', { name: 'Capture' })
    const button = dialog.querySelector('button[type=submit]') as HTMLButtonElement
    expect(button).toBeDisabled()
    await user.type(screen.getByLabelText('Thought'), 'Check the relay logs')
    await user.click(button)
    expect(await screen.findByRole('status')).toHaveTextContent('Saved capture as 00-Inbox/2026-10-06 1441 Check the relay logs.md')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('creates a task and names the Markdown file that is written', async () => {
    const user = userEvent.setup()
    renderInApp(<Harness />)
    await openAction(user, 'Task')
    await user.type(screen.getByLabelText('Title (becomes the file name)'), 'Renew certificate')
    expect(screen.getByText('Writes 02-Work/Tasks/Renew certificate.md')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Create task' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Created 02-Work/Tasks/Renew certificate.md from the task template')
  })

  it('adds a follow-up, creating the daily note first when it does not exist', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    renderInApp(<Harness />, client)
    await openAction(user, 'Follow-up')
    await user.type(screen.getByLabelText('Follow-up'), 'Ask infra for the refresh date')
    await user.click(screen.getByRole('button', { name: 'Add follow-up' }))
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Created 01-Daily/2026/2026-10-06.md from the daily template, then appended "Ask infra for the refresh date" under Follow-ups',
    )
    const standup = await client.getStandupToday()
    const lines = (standup.exists ? standup.note.body : '').split('\n')
    expect(lines).toContain('- [ ] Ask infra for the refresh date')
    expect(lines.some((l) => l.includes('- [ ] - [ ]'))).toBe(false)
  })

  it('fills an untouched standup with carry-forward before appending the line', async () => {
    const user = userEvent.setup()
    const client = mockClient({ standup: 'untouched' })
    renderInApp(<Harness />, client)
    await openAction(user, 'Follow-up')
    await user.type(screen.getByLabelText('Follow-up'), 'Ask infra')
    await user.click(screen.getByRole('button', { name: 'Add follow-up' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Filled 01-Daily/2026/2026-10-06.md with carry-forward, then appended "Ask infra"')
    const standup = await client.getStandupToday()
    expect(standup.exists && standup.note.body).toContain('- [ ] [[Investigate missing OTP email]]')
    expect(standup.exists && standup.note.body).toContain('- [ ] Ask infra')
  })

  it('shows the 409 message and keeps the dialog open', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    renderInApp(<Harness />, client)
    await openAction(user, 'Task')
    await user.type(screen.getByLabelText('Title (becomes the file name)'), 'Rotate staging API credentials')
    await user.click(screen.getByRole('button', { name: 'Create task' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('A note with this name already exists in 02-Work/Tasks. Nothing was written.')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await expect(client.createNote({ type: 'task', title: 'rotate staging api credentials' })).rejects.toBeInstanceOf(ApiError)
  })

  it('does not start a shortcut from a Select trigger or its open list', async () => {
    const user = userEvent.setup()
    renderInApp(
      <>
        <Select defaultValue="a">
          <SelectTrigger aria-label="Filter">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="a">alpha</SelectItem>
            <SelectItem value="d">delta</SelectItem>
          </SelectContent>
        </Select>
        <Harness />
      </>,
    )
    const combobox = screen.getByRole('combobox', { name: 'Filter' })
    combobox.focus()
    await user.keyboard('t')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.keyboard('{Enter}')
    await screen.findByRole('listbox')
    await user.keyboard('d')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('does not pre-select a project', async () => {
    const user = userEvent.setup()
    renderInApp(<Harness />)
    await openAction(user, 'Task')
    expect(screen.getByRole('combobox', { name: 'Project' })).toHaveTextContent('No project')
  })

  it('refreshes what is on screen after a write even when a later step fails', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    let projectCalls = 0
    const listProjects = client.listProjects
    client.listProjects = () => {
      projectCalls += 1
      return listProjects()
    }
    // The follow-up starts the standup (a write), then the append is rejected.
    client.appendToStandup = () => Promise.reject(new ApiError(409, 'changed in Obsidian'))
    function Probe() {
      const api = useApi()
      useQuery(useCallback(() => api.listProjects(), [api]))
      return null
    }
    renderInApp(
      <>
        <Probe />
        <Harness />
      </>,
      client,
    )
    await waitFor(() => expect(projectCalls).toBe(1))
    await openAction(user, 'Follow-up')
    await user.type(screen.getByLabelText('Follow-up'), 'Ask infra')
    await user.click(screen.getByRole('button', { name: 'Add follow-up' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('changed in Obsidian')
    await waitFor(() => expect(projectCalls).toBeGreaterThan(2))
  })
})

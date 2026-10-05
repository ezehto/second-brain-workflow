import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ApiError } from '@/api/client'
import { useCallback } from 'react'
import { useApi } from '@/api/ApiProvider'
import { useQuery } from '@/api/useQuery'
import { mockClient, renderInApp } from '@/test/helpers'
import { QuickActions } from './QuickActions'

describe('QuickActions', () => {
  it('has the five buttons', () => {
    renderInApp(<QuickActions />)
    const bar = screen.getByRole('toolbar', { name: 'Quick actions' })
    expect(bar.querySelectorAll('button')).toHaveLength(5)
    for (const name of ['Task', 'Follow-up', 'Decision', 'Note', 'Capture']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument()
    }
  })

  it('captures a thought and names the file in a toast', async () => {
    const user = userEvent.setup()
    renderInApp(<QuickActions />)
    await user.click(screen.getByRole('button', { name: 'Capture' }))
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
    renderInApp(<QuickActions />)
    await user.click(screen.getByRole('button', { name: 'Task' }))
    await user.type(screen.getByLabelText('Title (becomes the file name)'), 'Renew certificate')
    expect(screen.getByText('Writes 02-Work/Tasks/Renew certificate.md')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Create task' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Created 02-Work/Tasks/Renew certificate.md from the task template')
  })

  it('adds a follow-up, creating the daily note first when it does not exist', async () => {
    const user = userEvent.setup()
    renderInApp(<QuickActions />)
    await user.click(screen.getByRole('button', { name: 'Follow-up' }))
    await user.type(screen.getByLabelText('Follow-up'), 'Ask infra for the refresh date')
    await user.click(screen.getByRole('button', { name: 'Add follow-up' }))
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Created 01-Daily/2026/2026-10-06.md from the daily template, then appended "- [ ] Ask infra for the refresh date" under Follow-ups',
    )
  })

  it('fills an untouched standup with carry-forward before appending the line', async () => {
    const user = userEvent.setup()
    const client = mockClient({ standup: 'untouched' })
    renderInApp(<QuickActions />, client)
    await user.click(screen.getByRole('button', { name: 'Follow-up' }))
    await user.type(screen.getByLabelText('Follow-up'), 'Ask infra')
    await user.click(screen.getByRole('button', { name: 'Add follow-up' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Filled 01-Daily/2026/2026-10-06.md with carry-forward, then appended "- [ ] Ask infra"')
    const standup = await client.getStandupToday()
    expect(standup.exists && standup.note.body).toContain('- [ ] [[Investigate missing OTP email]]')
    expect(standup.exists && standup.note.body).toContain('- [ ] Ask infra')
  })

  it('shows the 409 message and keeps the dialog open', async () => {
    const user = userEvent.setup()
    const client = mockClient()
    renderInApp(<QuickActions />, client)
    await user.click(screen.getByRole('button', { name: 'Task' }))
    await user.type(screen.getByLabelText('Title (becomes the file name)'), 'Rotate staging API credentials')
    await user.click(screen.getByRole('button', { name: 'Create task' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('A note with this name already exists in 02-Work/Tasks. Nothing was written.')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await expect(client.createNote({ type: 'task', title: 'rotate staging api credentials' })).rejects.toBeInstanceOf(ApiError)
  })

  it('does not pre-select a project', async () => {
    const user = userEvent.setup()
    renderInApp(<QuickActions />)
    await user.click(screen.getByRole('button', { name: 'Task' }))
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
        <QuickActions />
      </>,
      client,
    )
    await waitFor(() => expect(projectCalls).toBe(1))
    await user.click(screen.getByRole('button', { name: 'Follow-up' }))
    await user.type(screen.getByLabelText('Follow-up'), 'Ask infra')
    await user.click(screen.getByRole('button', { name: 'Add follow-up' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('changed in Obsidian')
    await waitFor(() => expect(projectCalls).toBeGreaterThan(2))
  })
})

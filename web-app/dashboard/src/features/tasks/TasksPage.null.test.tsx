import { configure, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { createHttpClient } from '@/api/http'
import { renderRoutes } from '@/features/notes/testing'
import { mockClient } from '@/test/helpers'
import { TasksPage } from './TasksPage'

configure({ asyncUtilTimeout: 5000 })

const task = {
  id: null, path: '02-Work/Tasks/Bare task.md', type: 'task', title: 'Bare task', status: null,
  priority: null, project: null, due: null, blocked_by: null, decided: null, tags: [],
  created: null, modified: '2026-10-06T11:20:00+08:00', parse_error: null,
}

// The real wire shape, through the real client: null priority, status and due.
describe('null values from the API render as N/A', () => {
  it('shows N/A for a task with no priority and no status', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      new Response(JSON.stringify({ count: 1, next: null, previous: null, results: [task] }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    const base = mockClient()
    const client = { ...base, ...createHttpClient({ fetch: fetchMock }), listProjects: base.listProjects }
    renderRoutes([{ path: '/tasks', element: <TasksPage /> }], '/tasks', client)
    const row = (await screen.findByRole('link', { name: 'Bare task' })).closest('li')!
    // The priority mark and the status control each say N/A; a null due date shows nothing.
    expect(within(row).getAllByText('N/A')).toHaveLength(2)
  })
})

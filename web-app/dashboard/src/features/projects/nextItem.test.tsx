import { configure, screen, within } from '@testing-library/react'
import { useCallback } from 'react'
import { describe, expect, it } from 'vitest'
import { useApi } from '@/api/ApiProvider'
import { listAllNotes } from '@/api/listAll'
import { useQuery } from '@/api/useQuery'
import { ActiveProjects } from '@/features/dashboard/ActiveProjects'
import { renderRoutes } from '@/features/notes/testing'
import { mockClient } from '@/test/helpers'
import { task } from '@/test/notes'
import { ProjectPage } from './ProjectPage'
import { ProjectsPage } from './ProjectsPage'

configure({ asyncUtilTimeout: 5000 })

// LoadUp already has a blocked task; this planned one is overdue, so the Focus order puts it first.
const OVERDUE = 'Renew the provider contract'

function withOverdueTask() {
  const client = mockClient()
  const list = client.listNotes.bind(client)
  client.listNotes = async (params) => {
    const page = await list(params)
    if (params?.type !== 'task') return page
    const extra = task(OVERDUE, { project: 'loadup', status: 'planned', due: '2026-09-20', priority: 'high' })
    return { ...page, count: page.count + 1, results: [...page.results, extra] }
  }
  return client
}

function Dashboard() {
  const api = useApi()
  const projects = useQuery(useCallback(() => api.listProjects(), [api]))
  const tasks = useQuery(useCallback(() => listAllNotes(api, { type: 'task', ordering: 'path' }), [api]))
  return <ActiveProjects projects={projects} tasks={tasks} project={null} />
}

const routes = [
  { path: '/', element: <Dashboard /> },
  { path: '/projects', element: <ProjectsPage /> },
  { path: '/projects/:slug', element: <ProjectPage /> },
]

describe('the next item of a project', () => {
  it('is the same task on the Dashboard, the Projects list and the project page: the overdue one before the blocked one', async () => {
    const a = renderRoutes(routes, '/', withOverdueTask())
    const dashboardRow = (await screen.findByRole('link', { name: 'LoadUp' })).closest('div[class*="min-h"]') as HTMLElement
    expect(within(dashboardRow).getByRole('link', { name: OVERDUE })).toBeInTheDocument()
    expect(dashboardRow).toHaveTextContent(`Next: ${OVERDUE}`)
    a.unmount()

    const b = renderRoutes(routes, '/projects', withOverdueTask())
    const listRow = (await screen.findByRole('link', { name: 'LoadUp' })).closest('tr') as HTMLElement
    expect(await within(listRow).findByRole('link', { name: OVERDUE })).toBeInTheDocument()
    b.unmount()

    renderRoutes(routes, '/projects/loadup', withOverdueTask())
    const next = (await screen.findByRole('heading', { name: 'Next tasks' })).closest('section') as HTMLElement
    expect(within(next).getAllByRole('link')[0]).toHaveTextContent(OVERDUE)
  })
})

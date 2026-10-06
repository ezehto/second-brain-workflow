import type React from 'react'
import type { RouteObject } from 'react-router'
import { AppShell } from '@/components/AppShell'
import type { PageHandle } from '@/components/pageHandle'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { NotBuiltPage } from '@/features/placeholder/NotBuiltPage'
import { InboxPage } from '@/features/inbox'
import { IndexStatusPage } from '@/features/index-status'
import { DecisionsPage, KnowledgePage } from '@/features/knowledge'
import { ProjectPage, ProjectsPage } from '@/features/projects'
import { NotePage } from '@/features/notes'
import { TimelinePage, UpskillingPage, WorkflowPage } from '@/features/preview'
import { SearchPage } from '@/features/search'
import { StandupPage } from '@/features/standup'
import { TasksPage } from '@/features/tasks'
import { formatDayTitle } from '@/lib/dates'
import { routes } from '@/lib/routes'

const page = (title: string, subtitle: string): PageHandle => ({ title, subtitle })

/**
 * Route table. Each route's `handle` is what the shell header shows. A page
 * builder adds a real route above the catch-all and removes nothing else.
 */
export function createRoutes({ sampleData }: { sampleData: boolean }): RouteObject[] {
  const placeholder = (path: string, handle: PageHandle): RouteObject => ({ path, element: <NotBuiltPage />, handle })
  const real = (path: string, element: React.ReactElement, handle: PageHandle): RouteObject => ({ path, element, handle })
  return [
    {
      element: <AppShell sampleData={sampleData} />,
      children: [
        {
          index: true,
          element: <DashboardPage />,
          handle: {
            label: 'Today',
            title: ({ today }) => formatDayTitle(today),
            subtitle: ({ lastPass }) => (lastPass ? `Read from your vault at ${lastPass}, Manila time.` : 'Waiting for the first index pass.'),
          } satisfies PageHandle,
        },
        real(routes.standups, <StandupPage />, page('Standup', "Say it aloud from top to bottom, and write it into today's daily note.")),
        real(routes.inbox, <InboxPage />, page('Inbox', 'Captures waiting to be sorted.')),
        real(routes.tasks, <TasksPage />, page('Tasks', 'Every task note in 02-Work/Tasks, filtered and grouped.')),
        real(routes.projects, <ProjectsPage />, page('Projects', 'Every project with its health, open work and next item.')),
        real(`${routes.projects}/:slug`, <ProjectPage />, page('Project', 'One project and its tasks, decisions and notes.')),
        real(routes.workflow, <WorkflowPage />, page('Workflow', 'Where work sits across projects, and what a failure sends it back to.')),
        real(routes.timeline, <TimelinePage />, page('Timeline', 'What changed, in order, across the vault and the tools to be connected.')),
        real(routes.knowledge, <KnowledgePage />, page('Knowledge', 'Lessons from 05-Knowledge/Lessons.')),
        real(routes.decisions, <DecisionsPage />, page('Decisions', 'Decisions recorded in 05-Knowledge/Decisions.')),
        real(routes.upskilling, <UpskillingPage />, page('Upskilling', 'This week on the roadmap, and what real work says to learn next.')),
        real(routes.search, <SearchPage />, page('Search', 'Results come from the vault index.')),
        real(routes.indexStatus, <IndexStatusPage />, page('Index status', 'What the indexer read on its last pass.')),
        real('/notes', <NotePage />, page('Note', 'One note from the vault.')),
        placeholder('*', page('Page not found', 'There is nothing at this address.')),
      ],
    },
  ]
}

import type { RouteObject } from 'react-router'
import { AppShell } from '@/components/AppShell'
import type { PageHandle } from '@/components/pageHandle'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { NotBuiltPage } from '@/features/placeholder/NotBuiltPage'
import { formatDayTitle } from '@/lib/dates'
import { routes } from '@/lib/routes'

const page = (title: string, subtitle: string): PageHandle => ({ title, subtitle })

/**
 * Route table. Each route's `handle` is what the shell header shows. A page
 * builder adds a real route above the catch-all and removes nothing else.
 */
export function createRoutes({ sampleData }: { sampleData: boolean }): RouteObject[] {
  const placeholder = (path: string, handle: PageHandle): RouteObject => ({ path, element: <NotBuiltPage />, handle })
  return [
    {
      element: <AppShell sampleData={sampleData} />,
      children: [
        {
          index: true,
          element: <DashboardPage />,
          handle: {
            display: true,
            title: ({ today }) => formatDayTitle(today),
            subtitle: ({ lastPass }) => (lastPass ? `Read from your vault at ${lastPass}, Manila time.` : 'Waiting for the first index pass.'),
          } satisfies PageHandle,
        },
        placeholder(routes.standups, page('Standup', 'Daily notes and today\'s standup.')),
        placeholder(routes.inbox, page('Inbox', 'Captures waiting to be sorted.')),
        placeholder(routes.tasks, page('Tasks', 'Every task note in 02-Work/Tasks, filtered and grouped.')),
        placeholder(routes.projects, page('Projects', 'Health comes from a stated rule, not a score.')),
        placeholder(`${routes.projects}/:slug`, page('Project', 'One project and its tasks, decisions and notes.')),
        placeholder(routes.workflow, page('Workflow', 'Where work sits across projects.')),
        placeholder(routes.timeline, page('Timeline', 'What changed, in order.')),
        placeholder(routes.knowledge, page('Knowledge', 'Lessons from 05-Knowledge/Lessons.')),
        placeholder(routes.decisions, page('Decisions', 'Decisions recorded in 05-Knowledge/Decisions.')),
        placeholder(routes.upskilling, page('Upskilling', 'What you are learning and what to learn next.')),
        placeholder(routes.search, page('Search', 'Results come from the vault index.')),
        placeholder(routes.indexStatus, page('Index status', 'What the indexer read and what it could not.')),
        placeholder('/notes', page('Note', 'One note from the vault.')),
        placeholder('*', page('Page not found', 'There is nothing at this address.')),
      ],
    },
  ]
}

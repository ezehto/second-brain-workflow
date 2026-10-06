import { joinQueries, type Query } from '@/api/useQuery'
import type { DashboardResponse, NoteSummary } from '@/api/types'
import { ErrorState } from '@/components/ErrorState'
import { StatTile } from '@/components/StatTile'
import { inProject, proposedDecisions } from '@/domain/dashboard'
import { isOverdue } from '@/domain/tasks'
import { useToday } from '@/lib/clock'
import { withProject } from '@/lib/projectContext'
import { routes, tasksHref } from '@/lib/routes'

const LAYOUT = 'flex gap-3 overflow-x-auto sm:grid sm:grid-cols-3 sm:overflow-visible fullrail:grid-cols-6'
const TILE = 'min-w-40 flex-none sm:min-w-0'

/**
 * Six compact counts, each linking to the list it counts.
 *
 * In progress, Blocked and Overdue are counted from the same task list (and
 * the same `today`) as Focus and Blocked and waiting, so they cannot disagree.
 * "For today" (the standup carry-forward set) is a rule only the server
 * applies, so it comes from the aggregate, narrowed to the project context.
 * The inbox count is not narrowed: a capture has no project until triage.
 */
export function StatTiles({
  dashboard,
  tasks,
  decisions,
  project,
}: {
  dashboard: Query<DashboardResponse>
  tasks: Query<NoteSummary[]>
  decisions: Query<NoteSummary[]>
  project: string | null
}) {
  const today = useToday()
  const query = joinQueries(joinQueries(dashboard, tasks), decisions)
  if (query.status === 'loading') {
    return (
      <div role="status" className={LAYOUT}>
        <span className="sr-only">Loading</span>
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} aria-hidden="true" className={`${TILE} h-16 animate-pulse rounded-card border border-line bg-surface`} />
        ))}
      </div>
    )
  }
  if (query.status === 'error') {
    return (
      <div className="rounded-card border border-line bg-surface pt-3">
        <ErrorState message={query.error.message} onRetry={query.refetch} />
      </div>
    )
  }
  const [[d, all], decided] = query.data
  const link = (href: string) => withProject(href, project)
  return (
    <div className={LAYOUT}>
      <div className={TILE}>
        <StatTile compact icon="calendar" tone="brand" value={inProject(d.today_tasks, project).length} label="For today" to={link(tasksHref({ today: true }))} />
      </div>
      <div className={TILE}>
        <StatTile compact icon="clock" tone="progress" value={all.filter((t) => t.status === 'in-progress').length} label="In progress" to={link(tasksHref({ status: 'in-progress' }))} />
      </div>
      <div className={TILE}>
        <StatTile compact icon="blocked" tone="blocked" value={all.filter((t) => t.status === 'blocked').length} label="Blocked" to={link(tasksHref({ status: 'blocked' }))} />
      </div>
      <div className={TILE}>
        <StatTile compact icon="flag" tone="blocked" value={all.filter((t) => isOverdue(t, today)).length} label="Overdue" to={link(tasksHref({ status: 'open', overdue: true }))} />
      </div>
      <div className={TILE}>
        <StatTile compact icon="inbox" tone="neutral" value={d.inbox_count} label="In the inbox" to={routes.inbox} />
      </div>
      <div className={TILE}>
        <StatTile compact icon="decisions" tone="review" value={proposedDecisions(decided).length} label="Decisions pending" to={link(`${routes.decisions}?status=proposed`)} />
      </div>
    </div>
  )
}

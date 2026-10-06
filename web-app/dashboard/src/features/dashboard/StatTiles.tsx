import { joinQueries, type Query } from '@/api/useQuery'
import type { DashboardResponse, NoteSummary } from '@/api/types'
import { ErrorState } from '@/components/ErrorState'
import { StatTile } from '@/components/StatTile'
import { proposedDecisions } from '@/domain/dashboard'
import { isForToday, isOverdue } from '@/domain/tasks'
import { useToday } from '@/lib/clock'
import { useProjectHref } from '@/lib/projectContext'
import { routes } from '@/lib/routes'

/** Three by two on a phone, one row of six from 640px up (chips drop below 1280px, see `StatTile`). */
const LAYOUT = 'grid grid-cols-3 gap-2 sm:grid-cols-6 sm:gap-3'
const TILE = 'min-w-0'

/**
 * Six compact counts, each linking to the list it counts.
 *
 * For today (the standup carry-forward rule, `isForToday`), In progress,
 * Blocked and Overdue are all counted from the same task list and the same
 * `today` (`useToday()`) as Focus and Blocked and waiting, so they cannot
 * disagree. The inbox count is not narrowed: a capture has no project until triage.
 */
export function StatTiles({
  dashboard,
  tasks,
  decisions,
}: {
  dashboard: Query<DashboardResponse>
  tasks: Query<NoteSummary[]>
  decisions: Query<NoteSummary[]>
}) {
  const href = useProjectHref()
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
  return (
    <div className={LAYOUT}>
      <div className={TILE}>
        <StatTile compact condensed icon="calendar" tone="brand" value={all.filter((t) => isForToday(t, today)).length} label="For today" to={href.tasks({ today: true })} />
      </div>
      <div className={TILE}>
        <StatTile compact condensed icon="clock" tone="progress" value={all.filter((t) => t.status === 'in-progress').length} label="In progress" to={href.tasks({ status: 'in-progress' })} />
      </div>
      <div className={TILE}>
        <StatTile compact condensed icon="blocked" tone="blocked" value={all.filter((t) => t.status === 'blocked').length} label="Blocked" to={href.tasks({ status: 'blocked' })} />
      </div>
      <div className={TILE}>
        <StatTile compact condensed icon="flag" tone="blocked" value={all.filter((t) => isOverdue(t, today)).length} label="Overdue" to={href.tasks({ status: 'open', overdue: true })} />
      </div>
      <div className={TILE}>
        <StatTile compact condensed icon="inbox" tone="neutral" value={d.inbox_count} label="In the inbox" to={href.link(routes.inbox)} />
      </div>
      <div className={TILE}>
        <StatTile compact condensed icon="decisions" tone="review" value={proposedDecisions(decided).length} label="Decisions pending" to={href.link(`${routes.decisions}?status=proposed`)} />
      </div>
    </div>
  )
}

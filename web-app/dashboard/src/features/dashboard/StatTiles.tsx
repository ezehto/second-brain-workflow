import { joinQueries, type Query } from '@/api/useQuery'
import type { DashboardResponse, NoteSummary } from '@/api/types'
import { ErrorState } from '@/components/ErrorState'
import { StatTile } from '@/components/StatTile'
import { isOverdue } from '@/domain/tasks'
import { useToday } from '@/lib/clock'
import { routes, tasksHref } from '@/lib/routes'

const GRID = 'grid grid-cols-[repeat(auto-fit,minmax(min(160px,100%),1fr))] gap-4'

/**
 * Five counts, each linking to the list it counts.
 *
 * In progress, Blocked and Overdue are counted from the same task list that
 * Needs attention and the donut use, with the same `today`, so the tiles and
 * those sections cannot disagree. "For today" (the standup carry-forward set)
 * and the inbox count are rules only the server applies, so they come from
 * the aggregate.
 */
export function StatTiles({ dashboard, tasks }: { dashboard: Query<DashboardResponse>; tasks: Query<NoteSummary[]> }) {
  const today = useToday()
  const query = joinQueries(dashboard, tasks)
  if (query.status === 'loading') {
    return (
      <div role="status" className={GRID}>
        <span className="sr-only">Loading</span>
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} aria-hidden="true" className="h-[76px] animate-pulse rounded-card border border-line bg-surface" />
        ))}
      </div>
    )
  }
  if (query.status === 'error') {
    return (
      <div className="rounded-card border border-line bg-surface pt-5">
        <ErrorState message={query.error.message} onRetry={query.refetch} />
      </div>
    )
  }
  const [d, all] = query.data
  return (
    <div className={GRID}>
      <StatTile icon="calendar" tone="brand" value={d.today_tasks.length} label="For today" to={tasksHref({ today: true })} />
      <StatTile icon="clock" tone="progress" value={all.filter((t) => t.status === 'in-progress').length} label="In progress" to={tasksHref({ status: 'in-progress' })} />
      <StatTile icon="blocked" tone="blocked" value={all.filter((t) => t.status === 'blocked').length} label="Blocked" to={tasksHref({ status: 'blocked' })} />
      <StatTile icon="flag" tone="blocked" value={all.filter((t) => isOverdue(t, today)).length} label="Overdue" to={tasksHref({ status: 'open', overdue: true })} />
      <StatTile icon="inbox" tone="neutral" value={d.inbox_count} label="In the inbox" to={routes.inbox} />
    </div>
  )
}

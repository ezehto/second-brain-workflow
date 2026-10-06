import type { Query } from '@/api/useQuery'
import type { NoteSummary } from '@/api/types'
import { Card, CardHead } from '@/components/Card'
import { QueryBoundary } from '@/components/QueryBoundary'
import { TaskRow } from '@/components/TaskRow'
import { blockedTasks, daysSinceModified } from '@/domain/dashboard'
import type { ProjectLookup } from '@/domain/projects'
import { useToday } from '@/lib/clock'
import { NOT_AVAILABLE } from '@/lib/dates'
import { plural } from '@/lib/plural'

/**
 * What is stuck, and on what. Each row says what it waits on and for how long
 * (days since the note last changed). Focus already marks blocked work, so the
 * reason here is the blocker as written, not the word "Blocked" again.
 */
export function BlockedWaiting({ tasks, projects }: { tasks: Query<NoteSummary[]>; projects: ProjectLookup }) {
  const today = useToday()
  const blocked = tasks.status === 'success' ? blockedTasks(tasks.data) : []
  return (
    <Card aria-label="Blocked and waiting">
      <CardHead title="Blocked and waiting" count={tasks.status === 'success' ? blocked.length : undefined} />
      <QueryBoundary query={tasks} rows={2} isEmpty={() => blocked.length === 0} empty="Nothing is blocked.">
        {() =>
          blocked.map((t) => {
            const age = daysSinceModified(t, today)
            return (
              <TaskRow
                key={t.path}
                task={t}
                project={projects.title(t.project)}
                reason={t.blocked_by ?? NOT_AVAILABLE}
                status={<span className="num t-caption text-muted-ink">{age === 0 ? 'Since today' : plural(age, 'day')}</span>}
              />
            )
          })
        }
      </QueryBoundary>
    </Card>
  )
}

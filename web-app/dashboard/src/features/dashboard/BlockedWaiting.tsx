import type { Query } from '@/api/useQuery'
import type { NoteSummary } from '@/api/types'
import { Card, CardHead } from '@/components/Card'
import { QueryBoundary } from '@/components/QueryBoundary'
import { TaskRow } from '@/components/TaskRow'
import { blockedTasks, daysSinceModified } from '@/domain/dashboard'
import { todaysFocus } from '@/domain/focus'
import type { ProjectLookup } from '@/domain/projects'
import { useToday } from '@/lib/clock'
import { NOT_AVAILABLE } from '@/lib/dates'
import { plural } from '@/lib/plural'

/**
 * What is stuck, and on what. Each row says what it waits on and for how long
 * (days since the note last changed). Focus already marks blocked work, so the
 * reason here is the blocker as written, not the word "Blocked" again.
 *
 * A task Focus is already showing is not listed a second time. The count is
 * still every blocked task (it matches the Blocked tile), and the heading says
 * how many of them are in Focus.
 */
export function BlockedWaiting({ tasks, projects }: { tasks: Query<NoteSummary[]>; projects: ProjectLookup }) {
  const today = useToday()
  const blocked = tasks.status === 'success' ? blockedTasks(tasks.data) : []
  const inFocus = new Set(tasks.status === 'success' ? todaysFocus(tasks.data, today).map((item) => item.task.path) : [])
  const listed = blocked.filter((t) => !inFocus.has(t.path))
  const shownInFocus = blocked.length - listed.length
  return (
    <Card aria-label="Blocked and waiting">
      <CardHead title="Blocked and waiting" count={tasks.status === 'success' ? blocked.length : undefined}>
        {shownInFocus > 0 && <span className="t-small text-muted-ink">{shownInFocus} shown in Focus</span>}
      </CardHead>
      <QueryBoundary
        query={tasks}
        rows={2}
        isEmpty={() => listed.length === 0}
        empty={blocked.length === 0 ? 'Nothing is blocked.' : 'Every blocked task is already shown in Focus.'}
      >
        {() =>
          listed.map((t) => {
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

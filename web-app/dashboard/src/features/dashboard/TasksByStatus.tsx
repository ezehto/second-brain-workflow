import type { Query } from '@/api/useQuery'
import type { NoteSummary } from '@/api/types'
import { Card, CardHead } from '@/components/Card'
import { Donut } from '@/components/Donut'
import { QueryBoundary } from '@/components/QueryBoundary'
import { TASK_SEGMENT_COLOR } from '@/domain/status'
import { countByStatus, countUnknownStatus } from '@/domain/tasks'
import { plural } from '@/lib/plural'

/** How are all task notes spread across statuses? */
export function TasksByStatus({ tasks }: { tasks: Query<NoteSummary[]> }) {
  const total = tasks.status === 'success' ? tasks.data.length : null
  return (
    <Card>
      <CardHead title="Tasks by status" note={total === null ? undefined : `${total} task notes`} />
      <QueryBoundary query={tasks} isEmpty={(all) => all.length === 0} empty="No task notes in the vault yet.">
        {(all) => {
          const unknown = countUnknownStatus(all)
          return (
            <>
              <Donut
                segments={countByStatus(all).map((s) => ({ label: s.status, count: s.count, color: TASK_SEGMENT_COLOR[s.status] }))}
                total={all.length - unknown}
                centerLabel="tasks"
                ariaLabel={`Tasks by status, ${all.length - unknown} task notes`}
              />
              {unknown > 0 && (
                <p className="note m-0 px-5 pb-4">
                  {plural(unknown, 'task')} with a status outside the vocabulary {unknown === 1 ? 'is' : 'are'} not counted. See Index status.
                </p>
              )}
            </>
          )
        }}
      </QueryBoundary>
    </Card>
  )
}

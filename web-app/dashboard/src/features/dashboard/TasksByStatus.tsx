import type { Query } from '@/api/useQuery'
import type { NoteSummary } from '@/api/types'
import { Card, CardHead } from '@/components/Card'
import { Donut } from '@/components/Donut'
import { QueryBoundary } from '@/components/QueryBoundary'
import { TASK_SEGMENT_COLOR } from '@/domain/status'
import { countByStatus, countUnknownStatus } from '@/domain/tasks'
import { plural } from '@/lib/plural'

/** Where do all tasks stand? A 120px donut with its legend of counts (chart 1). */
export function TasksByStatus({ tasks }: { tasks: Query<NoteSummary[]> }) {
  return (
    <Card aria-label="Tasks by status">
      <CardHead title="Where do my tasks stand?" count={tasks.status === 'success' ? tasks.data.length : undefined} />
      <QueryBoundary query={tasks} isEmpty={(all) => all.length === 0} empty="No task notes yet.">
        {(all) => {
          const unknown = countUnknownStatus(all)
          return (
            <>
              <Donut
                size={120}
                className="flex flex-wrap items-center gap-4 px-3 pb-3"
                segments={countByStatus(all).map((s) => ({ label: s.status, count: s.count, color: TASK_SEGMENT_COLOR[s.status] }))}
                total={all.length - unknown}
                centerLabel="tasks"
                ariaLabel={`Tasks by status, ${all.length - unknown} task notes`}
              />
              {unknown > 0 && (
                <p className="note m-0 px-3 pb-3">
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

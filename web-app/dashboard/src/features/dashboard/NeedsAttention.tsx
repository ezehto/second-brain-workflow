import { Link } from 'react-router'
import type { Query } from '@/api/useQuery'
import type { NoteSummary } from '@/api/types'
import { Card, CardHead, CardRow } from '@/components/Card'
import { QueryBoundary } from '@/components/QueryBoundary'
import { attentionRows, type AttentionRow } from '@/domain/attention'
import type { ProjectLookup } from '@/domain/projects'
import { TONE_TEXT } from '@/domain/status'
import { useToday } from '@/lib/clock'
import { NOT_AVAILABLE } from '@/lib/dates'
import { noteHref } from '@/lib/routes'

function countClass(row: AttentionRow) {
  return row.key === 'high-priority' && row.count ? 'text-ink' : TONE_TEXT[row.tone]
}

/** Blocked, overdue, high priority, in review, and incidents (not tracked yet: `N/A`). */
export function NeedsAttention({ tasks, projects }: { tasks: Query<NoteSummary[]>; projects: ProjectLookup }) {
  const today = useToday()
  return (
    <Card className="flex-[1_1_340px]">
      <CardHead title="Needs attention" />
      <QueryBoundary query={tasks} rows={4}>
        {(all) =>
          attentionRows(all, today, projects.title).map((row) => (
            <CardRow key={row.key} className="grid-cols-1 items-start gap-1.5">
              <div className="flex items-baseline gap-2.5">
                <span className={`num text-xl font-extrabold ${countClass(row)}`}>{row.count ?? NOT_AVAILABLE}</span>
                {row.to ? (
                  <Link to={row.to} className="linkbtn">
                    {row.label}
                  </Link>
                ) : (
                  <span className="font-semibold">{row.label}</span>
                )}
              </div>
              <div className="flex min-w-0 flex-col gap-[3px]">
                {row.items.map(({ task, note }) => (
                  <span key={task.path}>
                    <Link to={noteHref(task.path)} className="linkbtn font-medium">
                      {task.title}
                    </Link>{' '}
                    <span className="text-[13px] text-muted-ink">{note}</span>
                  </span>
                ))}
                {row.items.length === 0 && <span className="text-muted-ink">{row.emptyText}</span>}
              </div>
            </CardRow>
          ))
        }
      </QueryBoundary>
    </Card>
  )
}

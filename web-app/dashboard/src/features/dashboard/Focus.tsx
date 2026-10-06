import { Link } from 'react-router'
import type { Query } from '@/api/useQuery'
import type { NoteSummary } from '@/api/types'
import { Card, CardHead } from '@/components/Card'
import { QueryBoundary } from '@/components/QueryBoundary'
import { StatusMenu } from '@/components/StatusMenu'
import { TaskRow } from '@/components/TaskRow'
import { Button } from '@/components/ui/button'
import { FOCUS_RULE, todaysFocus } from '@/domain/focus'
import type { ProjectLookup } from '@/domain/projects'
import { useToday } from '@/lib/clock'
import { withProject } from '@/lib/projectContext'
import { tasksHref } from '@/lib/routes'
import { InfoTip } from './InfoTip'

/**
 * The hero panel: up to five tasks by a fixed, stated rule (the rule is in the
 * "i" tooltip). The first row is marked "Next". Status changes in place.
 */
export function Focus({ tasks, projects, project }: { tasks: Query<NoteSummary[]>; projects: ProjectLookup; project: string | null }) {
  const today = useToday()
  const items = tasks.status === 'success' ? todaysFocus(tasks.data, today) : []
  return (
    <Card aria-label="Focus">
      <CardHead title="Focus" count={tasks.status === 'success' ? items.length : undefined}>
        <InfoTip label="How focus is chosen" rule={FOCUS_RULE} />
        <Button asChild variant="secondary" size="sm">
          <Link to={withProject(tasksHref(), project)}>All tasks</Link>
        </Button>
      </CardHead>
      <QueryBoundary query={tasks} rows={4} isEmpty={() => items.length === 0} empty="Nothing is overdue, blocked, due today or in review.">
        {() =>
          items.map((item) => (
            <TaskRow
              key={item.task.path}
              task={item.task}
              project={projects.title(item.task.project)}
              reason={
                <>
                  {item.rank === 1 && <span className="font-semibold text-ink">Next. </span>}
                  {item.reason}
                </>
              }
              status={<StatusMenu note={item.task} />}
            />
          ))
        }
      </QueryBoundary>
    </Card>
  )
}

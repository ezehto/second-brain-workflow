import { Link } from 'react-router'
import type { Query } from '@/api/useQuery'
import type { NoteSummary } from '@/api/types'
import { AccentCard, CardFootnote, CardHead, CardRow } from '@/components/Card'
import { QueryBoundary } from '@/components/QueryBoundary'
import { StatusChip } from '@/components/StatusChip'
import { Button } from '@/components/ui/button'
import { FOCUS_RULE, todaysFocus } from '@/domain/focus'
import type { ProjectLookup } from '@/domain/projects'
import { useToday } from '@/lib/clock'
import { noteHref, projectHref, tasksHref } from '@/lib/routes'

/** The page's one accent card: up to five tasks by a fixed, stated rule. */
export function TodaysFocus({ tasks, projects }: { tasks: Query<NoteSummary[]>; projects: ProjectLookup }) {
  const today = useToday()
  return (
    <AccentCard>
      <CardHead title="Today's focus">
        <Button asChild variant="onAccent" size="sm">
          <Link to={tasksHref()}>All tasks</Link>
        </Button>
      </CardHead>
      <QueryBoundary
        query={tasks}
        rows={4}
        isEmpty={(all) => todaysFocus(all, today).length === 0}
        empty={<span className="text-brand-on-fill">Nothing is overdue, blocked, due today or in review.</span>}
      >
        {(all) => (
          <ol className="m-0 list-none p-0">
            {todaysFocus(all, today).map((item) => (
              <li key={item.task.path}>
                <CardRow className="grid-cols-[26px_minmax(0,1fr)_auto] border-white/20">
                  <span aria-hidden="true" className="num inline-flex size-6 items-center justify-center rounded-full bg-white/20 text-xs font-bold">
                    {item.rank}
                  </span>
                  <div className="flex min-w-0 flex-col gap-px">
                    <Link to={noteHref(item.task.path)} className="linkbtn text-white hover:text-white">
                      {item.task.title}
                    </Link>
                    <span className="text-[13px]">
                      <span className="font-semibold">{item.reason}.</span>{' '}
                      {projects.known(item.task.project) ? (
                        <Link to={projectHref(item.task.project as string)} className="text-brand-on-fill underline hover:text-white">
                          {projects.title(item.task.project)}
                        </Link>
                      ) : (
                        <span className="text-brand-on-fill">{projects.title(item.task.project)}</span>
                      )}
                    </span>
                  </div>
                  <StatusChip status={item.task.status} />
                </CardRow>
              </li>
            ))}
          </ol>
        )}
      </QueryBoundary>
      <CardFootnote accent>{FOCUS_RULE}</CardFootnote>
    </AccentCard>
  )
}

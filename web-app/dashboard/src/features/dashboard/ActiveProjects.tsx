import { Link } from 'react-router'
import { joinQueries, type Query } from '@/api/useQuery'
import type { NoteSummary, ProjectSummary } from '@/api/types'
import { Card, CardHead, CardRow } from '@/components/Card'
import { ProgressBar } from '@/components/ProgressBar'
import { QueryBoundary } from '@/components/QueryBoundary'
import { StatusChip } from '@/components/StatusChip'
import { Button } from '@/components/ui/button'
import { nextTask } from '@/domain/focus'
import { HEALTH_RULE, projectHealth, projectProgress } from '@/domain/health'
import { useToday } from '@/lib/clock'
import { useProjectHref } from '@/lib/projectContext'
import { routes } from '@/lib/routes'
import { InfoTip } from './InfoTip'

/** One ruled row per active project: health word with its reason, the blocked or next item, progress as counts. */
export function ActiveProjects({
  projects,
  tasks,
  project,
}: {
  projects: Query<ProjectSummary[]>
  tasks: Query<NoteSummary[]>
  /** Project context: only this project (if active), or all active projects. */
  project: string | null
}) {
  const href = useProjectHref()
  const today = useToday()
  const visible = (list: ProjectSummary[]) => list.filter((p) => p.status === 'active' && (!project || p.slug === project))
  return (
    <Card aria-label="Active projects">
      <CardHead title="Active projects" count={projects.status === 'success' ? visible(projects.data).length : undefined}>
        <InfoTip label="How project health is decided" rule={HEALTH_RULE} />
        <Button asChild variant="secondary" size="sm">
          <Link to={href.link(routes.projects)}>All projects</Link>
        </Button>
      </CardHead>
      <QueryBoundary query={joinQueries(projects, tasks)} isEmpty={([list]) => visible(list).length === 0} empty="No active projects.">
        {([list, all]) =>
          visible(list).map((p) => {
            const mine = all.filter((t) => t.project === p.slug)
            const health = projectHealth(p, mine, today)
            const progress = projectProgress(mine)
            const item = nextTask(mine, today)
            return (
              <CardRow key={p.slug} lines={2} className="grid-cols-[minmax(0,1fr)_auto] py-1.5">
                <div className="flex min-w-0 flex-col">
                  <div className="flex min-w-0 flex-wrap items-center gap-x-2">
                    <Link to={href.project(p.slug)} className="linkbtn t-body">
                      {p.title}
                    </Link>
                    <StatusChip label={health.label} tone={health.tone} />
                    <span className="t-small text-muted-ink">{health.reason}</span>
                  </div>
                  <span className="t-small truncate text-muted-ink">
                    {item ? (
                      <>
                        {item.status === 'blocked' ? 'Blocked: ' : 'Next: '}
                        <Link to={href.note(item.path)} className="linkbtn t-small font-normal">
                          {item.title}
                        </Link>
                      </>
                    ) : (
                      'No open tasks.'
                    )}
                  </span>
                </div>
                <div className="flex w-28 flex-col items-end gap-1">
                  <span className="num t-small text-muted-ink">{progress.text}</span>
                  <div className="flex w-full">
                    <ProgressBar percent={progress.percent} label={`${p.title} progress`} />
                  </div>
                </div>
              </CardRow>
            )
          })
        }
      </QueryBoundary>
    </Card>
  )
}

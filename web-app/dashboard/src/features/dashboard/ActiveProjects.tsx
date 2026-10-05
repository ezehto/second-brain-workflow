import { Link } from 'react-router'
import { joinQueries, type Query } from '@/api/useQuery'
import type { NoteSummary, ProjectSummary } from '@/api/types'
import { Card, CardFootnote, CardHead, CardRow } from '@/components/Card'
import { ProgressBar } from '@/components/ProgressBar'
import { QueryBoundary } from '@/components/QueryBoundary'
import { StatusChip } from '@/components/StatusChip'
import { Button } from '@/components/ui/button'
import { HEALTH_RULE, projectHealth, projectProgress } from '@/domain/health'
import { useToday } from '@/lib/clock'
import { projectHref, routes } from '@/lib/routes'

/** Each active project with its health (a stated rule) and progress as counts. */
export function ActiveProjects({ projects, tasks }: { projects: Query<ProjectSummary[]>; tasks: Query<NoteSummary[]> }) {
  const today = useToday()
  return (
    <Card>
      <CardHead title="Active projects">
        <Button asChild variant="secondary" size="sm">
          <Link to={routes.projects}>All projects</Link>
        </Button>
      </CardHead>
      <QueryBoundary
        query={joinQueries(projects, tasks)}
        isEmpty={([list]) => list.filter((p) => p.status === 'active').length === 0}
        empty="No active projects."
      >
        {([list, all]) =>
          list
            .filter((p) => p.status === 'active')
            .map((project) => {
              const mine = all.filter((t) => t.project === project.slug)
              const health = projectHealth(project, mine, today)
              const progress = projectProgress(mine)
              return (
                <CardRow key={project.slug} className="grid-cols-1 gap-2">
                  <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                    <Link to={projectHref(project.slug)} className="linkbtn">
                      {project.title}
                    </Link>
                    <StatusChip label={health.label} tone={health.tone} />
                  </div>
                  <div className="text-[13px] text-muted-ink">{health.reason}</div>
                  <div className="flex items-center gap-3">
                    <ProgressBar percent={progress.percent} label={`${project.title} progress`} />
                    <span className="num flex-none text-[13px] text-muted-ink">{progress.text}</span>
                  </div>
                </CardRow>
              )
            })
        }
      </QueryBoundary>
      <CardFootnote>{HEALTH_RULE}</CardFootnote>
    </Card>
  )
}

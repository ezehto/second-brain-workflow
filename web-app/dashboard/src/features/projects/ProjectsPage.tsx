import { useCallback, useMemo } from 'react'
import { Link } from 'react-router'
import { useApi } from '@/api/ApiProvider'
import { listAllNotes } from '@/api/listAll'
import { joinQueries, useQuery } from '@/api/useQuery'
import type { NoteSummary, ProjectSummary } from '@/api/types'
import { Card, CardHead, CardRow } from '@/components/Card'
import { QueryBoundary } from '@/components/QueryBoundary'
import { StatusChip } from '@/components/StatusChip'
import { nextTask } from '@/domain/focus'
import { projectHealth, type ProjectHealth } from '@/domain/health'
import { useMinWidth } from '@/lib/viewport'
import { useToday } from '@/lib/clock'
import { NOT_AVAILABLE, formatWhen } from '@/lib/dates'
import { useProjectContext, useProjectHref } from '@/lib/projectContext'
import { cn } from '@/lib/utils'
import { HEALTH_SEVERITY, lastActivity, projectCounts, type ProjectCounts } from './domain'
import { HealthRule } from './HealthRule'

interface Row {
  project: ProjectSummary
  health: ProjectHealth
  counts: ProjectCounts
  next: NoteSummary | null
  last: string
}

const count = (n: number, hot: boolean) => (
  <span className={cn('num', n === 0 ? 'text-muted-ink' : hot && 'font-semibold text-status-blocked')}>{n}</span>
)

const TH = 't-small h-8 px-3 text-left font-semibold text-muted-ink'
const TD = 'h-8 px-3 align-middle'

function Table({ rows, selected, today }: { rows: Row[]; selected: string | null; today: string }) {
  const href = useProjectHref()
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead className="bg-inset">
          <tr>
            <th scope="col" className={TH}>Project</th>
            <th scope="col" className={TH}>Status</th>
            <th scope="col" className={TH}>Health</th>
            <th scope="col" className={cn(TH, 'text-right')}>Open</th>
            <th scope="col" className={cn(TH, 'text-right')}>Blocked</th>
            <th scope="col" className={cn(TH, 'text-right')}>Overdue</th>
            <th scope="col" className={TH}>Next item</th>
            <th scope="col" className={cn(TH, 'text-right')}>Last activity</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ project, health, counts, next, last }) => (
            <tr key={project.slug} aria-current={selected === project.slug ? 'true' : undefined} className={cn('border-t border-line', selected === project.slug && 'bg-inset')}>
              <th scope="row" className={cn(TD, 'text-left font-normal')}>
                <Link to={href.project(project.slug)} className="linkbtn t-body whitespace-nowrap">
                  {project.title}
                </Link>
              </th>
              <td className={TD}>
                <StatusChip status={project.status} />
              </td>
              <td className={TD}>
                <span className="flex items-center gap-2 whitespace-nowrap">
                  <StatusChip label={health.label} tone={health.tone} />
                  <span className="t-small text-muted-ink">{health.reason}</span>
                </span>
              </td>
              <td className={cn(TD, 'text-right')}>{count(counts.open, false)}</td>
              <td className={cn(TD, 'text-right')}>{count(counts.blocked, true)}</td>
              <td className={cn(TD, 'text-right')}>{count(counts.overdue, true)}</td>
              <td className={cn(TD, 'max-w-72')}>
                {next ? (
                  <Link to={href.note(next.path)} className="t-body block truncate">
                    {next.title}
                  </Link>
                ) : (
                  <span className="text-muted-ink">{NOT_AVAILABLE}</span>
                )}
              </td>
              <td className={cn(TD, 'num t-small text-right whitespace-nowrap text-muted-ink')}>{formatWhen(last, today)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Phones: two-line rows (name and health, then the counts) so nothing is wider than the screen. */
function PhoneList({ rows, selected }: { rows: Row[]; selected: string | null }) {
  const href = useProjectHref()
  return (
    <ul className="m-0 list-none p-0">
      {rows.map(({ project, health, counts, next }) => (
        <li key={project.slug}>
          <CardRow lines={2} aria-current={selected === project.slug ? 'true' : undefined} className={cn('grid-cols-[minmax(0,1fr)_auto]', selected === project.slug && 'bg-inset')}>
            <div className="flex min-w-0 flex-col">
              <Link to={href.project(project.slug)} className="linkbtn t-body truncate">
                {project.title}
              </Link>
              <span className="t-small truncate text-muted-ink">
                {counts.open} open, {counts.blocked} blocked, {counts.overdue} overdue
                {next ? `, next: ${next.title}` : ''}
              </span>
            </div>
            <StatusChip label={health.label} tone={health.tone} />
          </CardRow>
        </li>
      ))}
    </ul>
  )
}

/**
 * Which projects need attention? One dense table, sorted by health severity
 * then name. The `project` context parameter marks a row as selected.
 */
export function ProjectsPage() {
  const client = useApi()
  const today = useToday()
  const selected = useProjectContext()
  const roomy = useMinWidth(640)
  const projects = useQuery(useCallback(() => client.listProjects(), [client]))
  const tasks = useQuery(useCallback(() => listAllNotes(client, { type: 'task', ordering: 'path' }), [client]))
  const query = useMemo(() => joinQueries(projects, tasks), [projects, tasks])

  return (
    <Card>
      <CardHead title="Projects" count={projects.status === 'success' ? projects.data.length : undefined}>
        <HealthRule />
      </CardHead>
      <QueryBoundary
        query={query}
        rows={4}
        isEmpty={([list]) => list.length === 0}
        empty="No project notes yet. Use New in the header to create a project, or add a note to 02-Work/Projects in Obsidian."
      >
        {([list, all]) => {
          const rows: Row[] = list
            .map((project) => {
              const mine = all.filter((t) => t.project === project.slug)
              return {
                project,
                health: projectHealth(project, mine, today),
                counts: projectCounts(mine, today),
                next: nextTask(mine, today),
                last: lastActivity(project.modified, mine),
              }
            })
            .sort((a, b) => HEALTH_SEVERITY[a.health.label] - HEALTH_SEVERITY[b.health.label] || a.project.title.localeCompare(b.project.title))
          return roomy ? <Table rows={rows} selected={selected} today={today} /> : <PhoneList rows={rows} selected={selected} />
        }}
      </QueryBoundary>
    </Card>
  )
}

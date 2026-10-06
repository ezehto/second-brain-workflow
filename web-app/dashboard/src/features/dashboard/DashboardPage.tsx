import { useCallback, useMemo, type ReactNode } from 'react'
import { useApi } from '@/api/ApiProvider'
import { listAllNotes } from '@/api/listAll'
import { useQuery, type Query } from '@/api/useQuery'
import { useShellDashboard } from '@/components/ShellData'
import { inProject } from '@/domain/dashboard'
import { projectLookup } from '@/domain/projects'
import { useMinWidth } from '@/lib/viewport'
import { useProjectContext } from '@/lib/projectContext'
import { ActiveProjects } from './ActiveProjects'
import { BlockedWaiting } from './BlockedWaiting'
import { DecisionsToMake } from './DecisionsToMake'
import { DoneRecently } from './DoneRecently'
import { Focus } from './Focus'
import { Learning } from './Learning'
import { Schedule } from './Schedule'
import { StandupPanel } from './StandupPanel'
import { StatTiles } from './StatTiles'
import { TasksByStatus } from './TasksByStatus'
import { WorkflowStrip } from './WorkflowStrip'

/** Viewport widths from which the panels use two and three columns (the rail changes at 832 and 1280). */
const TWO_COLUMNS = 1024
const THREE_COLUMNS = 1700

/** A query's data narrowed to the project context, keeping its state. */
function narrowed<T extends { project: string | null }>(query: Query<T[]>, project: string | null): Query<T[]> {
  return query.status === 'success' ? { ...query, data: inProject(query.data, project) } : query
}

/**
 * Today. A strip of six counts, then panels in the order of the request:
 * decide, prioritise, execute, record. Three columns at 1920, two at 1440, one
 * on a phone (where the order is the phone order of the assessment, 5.6).
 * Every panel follows the project context (`?project=`).
 */
export function DashboardPage() {
  const client = useApi()
  const project = useProjectContext()
  const dashboard = useShellDashboard()
  const projects = useQuery(useCallback(() => client.listProjects(), [client]))
  const allTasks = useQuery(useCallback(() => listAllNotes(client, { type: 'task', ordering: 'path' }), [client]))
  const allDecisions = useQuery(useCallback(() => listAllNotes(client, { type: 'decision', ordering: 'path' }), [client]))
  const three = useMinWidth(THREE_COLUMNS, false)
  const two = useMinWidth(TWO_COLUMNS, false)

  const tasks = useMemo(() => narrowed(allTasks, project), [allTasks, project])
  const decisions = useMemo(() => narrowed(allDecisions, project), [allDecisions, project])
  const lookup = useMemo(() => projectLookup(projects.status === 'success' ? projects.data : undefined), [projects])

  const panels: Record<string, ReactNode> = {
    focus: <Focus key="focus" tasks={tasks} projects={lookup} />,
    blocked: <BlockedWaiting key="blocked" tasks={tasks} projects={lookup} />,
    decisions: <DecisionsToMake key="decisions" decisions={decisions} projects={lookup} />,
    standup: <StandupPanel key="standup" dashboard={dashboard} projects={projects} tasks={allTasks} />,
    projects: <ActiveProjects key="projects" projects={projects} tasks={allTasks} project={project} />,
    status: <TasksByStatus key="status" tasks={tasks} />,
    done: <DoneRecently key="done" tasks={tasks} />,
    schedule: <Schedule key="schedule" />,
    learning: <Learning key="learning" />,
  }
  const layout: string[][] = three
    ? [
        ['focus', 'projects', 'status'],
        ['blocked', 'decisions', 'done'],
        ['standup', 'schedule', 'learning'],
      ]
    : two
      ? [
          ['focus', 'projects', 'status', 'schedule', 'learning'],
          ['blocked', 'decisions', 'standup', 'done'],
        ]
      : [['focus', 'blocked', 'decisions', 'standup', 'projects', 'done', 'status', 'schedule', 'learning']]

  const widths = three ? 'grid-cols-[5fr_4fr_3fr]' : two ? 'grid-cols-[7fr_5fr]' : 'grid-cols-1'

  return (
    <div className="flex flex-col gap-4">
      <StatTiles dashboard={dashboard} tasks={tasks} decisions={decisions} />
      <div className={`grid items-start gap-4 ${widths}`}>
        {layout.map((column) => (
          <div key={column.join('-')} className="flex min-w-0 flex-col gap-4">
            {column.map((id) => panels[id])}
          </div>
        ))}
      </div>
      <WorkflowStrip />
    </div>
  )
}

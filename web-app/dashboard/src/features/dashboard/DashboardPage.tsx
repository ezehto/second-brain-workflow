import { useCallback, useMemo } from 'react'
import { useApi } from '@/api/ApiProvider'
import { listAllNotes } from '@/api/listAll'
import { useQuery, type Query } from '@/api/useQuery'
import type { NoteSummary } from '@/api/types'
import { useShellDashboard } from '@/components/ShellData'
import { projectLookup } from '@/domain/projects'
import { ActiveProjects } from './ActiveProjects'
import { Improving } from './Improving'
import { Integrations } from './Integrations'
import { NeedsAttention } from './NeedsAttention'
import { RecentActivity } from './RecentActivity'
import { StatTiles } from './StatTiles'
import { TasksByStatus } from './TasksByStatus'
import { TodaysFocus } from './TodaysFocus'
import { TodaysMeetings } from './TodaysMeetings'
import { TodaysStandup } from './TodaysStandup'
import { WorkflowStages } from './WorkflowStages'

/**
 * The dashboard. Real Phase 1 sections read the shell's dashboard aggregate,
 * the full task list (every page of it) and the project list; the meetings,
 * workflow, learning and integrations sections render `src/preview` data and
 * say so.
 */
export function DashboardPage() {
  const client = useApi()
  const dashboard = useShellDashboard()
  const projects = useQuery(useCallback(() => client.listProjects(), [client]))
  const tasks: Query<NoteSummary[]> = useQuery(useCallback(() => listAllNotes(client, { type: 'task', ordering: 'path' }), [client]))
  const lookup = useMemo(() => projectLookup(projects.status === 'success' ? projects.data : undefined), [projects])

  return (
    <div className="flex flex-col gap-5">
      <StatTiles dashboard={dashboard} tasks={tasks} />

      <div className="flex flex-wrap items-start gap-5">
        <div className="flex min-w-0 flex-[2_1_480px] flex-col gap-5">
          <TodaysFocus tasks={tasks} projects={lookup} />
          <TasksByStatus tasks={tasks} />
        </div>
        <NeedsAttention tasks={tasks} projects={lookup} />
      </div>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(340px,100%),1fr))] items-start gap-5">
        <ActiveProjects projects={projects} tasks={tasks} />
        <div className="flex min-w-0 flex-col gap-5">
          <TodaysMeetings />
          <TodaysStandup query={dashboard} />
        </div>
      </div>

      <WorkflowStages />

      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(340px,100%),1fr))] items-start gap-5">
        <RecentActivity query={dashboard} />
        <Improving />
        <Integrations />
      </div>
    </div>
  )
}

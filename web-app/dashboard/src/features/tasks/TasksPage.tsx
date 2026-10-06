import { useCallback, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useApi } from '@/api/ApiProvider'
import { listAllNotes } from '@/api/listAll'
import { TASK_STATUSES, type NoteSummary } from '@/api/types'
import { useQuery } from '@/api/useQuery'
import { Card, CardHead } from '@/components/Card'
import { EmptyState } from '@/components/EmptyState'
import { QueryBoundary } from '@/components/QueryBoundary'
import { isOpen } from '@/domain/tasks'
import { projectLookup } from '@/domain/projects'
import { useToday } from '@/lib/clock'
import { tasksHref, type TaskFilters } from '@/lib/routes'
import { NoteReader } from '@/features/notes/NoteReader'
import { SplitPane } from '@/features/notes/SplitPane'
import { useMinWidth, useSplitLayout } from '@/lib/viewport'
import { FilterBar } from './FilterBar'
import { StatusBar } from './StatusBar'
import { TaskTable } from './TaskTable'
import { applyTaskFilters, buildTaskParams, parseTaskParams, type GroupBy, type TaskView } from './filters'
import { groupTasks } from './grouping'

/**
 * The Tasks page: every task note, filtered by the URL (`lib/routes.ts`
 * contract), grouped by project, status or due date, with the status
 * distribution as the status filter. Selecting a row opens the note in a split
 * pane from 1024 up, or on its own route below that.
 */
export function TasksPage() {
  const client = useApi()
  const today = useToday()
  const [params, setParams] = useSearchParams()
  const view = useMemo(() => parseTaskParams(params), [params])
  const split = useSplitLayout()
  const roomy = useMinWidth(640)

  const tasks = useQuery(useCallback(() => listAllNotes(client, { type: 'task', ordering: 'path' }), [client]))
  const projects = useQuery(useCallback(() => client.listProjects(), [client]))
  const projectList = projects.status === 'success' ? projects.data : []
  const lookup = useMemo(() => projectLookup(projects.status === 'success' ? projects.data : undefined), [projects])

  const update = (next: Partial<TaskView>) => setParams(buildTaskParams({ ...view, ...next }))
  const setFilters = (change: Partial<TaskFilters>) => update({ filters: { ...view.filters, ...change }, note: view.note })

  const open = split ? (task: NoteSummary) => update({ note: task.path }) : undefined
  const reader = split && view.note ? <NoteReader path={view.note} onClose={() => update({ note: undefined })} /> : undefined

  return (
    <div className="flex flex-col gap-4">
      <QueryBoundary
        query={tasks}
        rows={5}
        isEmpty={(all) => all.length === 0}
        empty={<>No task notes yet. Use New in the header to create one, or add a note to 02-Work/Tasks in Obsidian.</>}
      >
        {(all) => {
          const base = applyTaskFilters(all, view.filters, today, { ignoreStatus: true })
          const counts = Object.fromEntries(TASK_STATUSES.map((s) => [s, base.filter((t) => t.status === s).length]))
          const shown = applyTaskFilters(all, view.filters, today)
          const groups = groupTasks(shown, view.group, today, lookup)
          return (
            <>
              <StatusBar
                counts={counts}
                open={base.filter(isOpen).length}
                total={base.length}
                value={view.filters.status}
                onChange={(status) => setFilters({ status })}
              />
              <FilterBar
                filters={view.filters}
                group={view.group}
                projects={projectList}
                onFilters={setFilters}
                onGroup={(group: GroupBy) => update({ group })}
              />
              <SplitPane
                reader={reader}
                readerLabel="Open note"
                list={
                  <Card>
                    <CardHead title="Tasks" count={shown.length} />
                    {groups.length === 0 ? (
                      <EmptyState className="border-t border-line pt-3" action={<Link to={tasksHref()}>Clear filters</Link>}>
                        No tasks match these filters.
                      </EmptyState>
                    ) : (
                      <TaskTable groups={groups} by={view.group} projects={lookup} phone={!roomy} selectedPath={view.note} onOpen={open} />
                    )}
                  </Card>
                }
              />
            </>
          )
        }}
      </QueryBoundary>
    </div>
  )
}

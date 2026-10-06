import { useCallback, useMemo } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { useApi } from '@/api/ApiProvider'
import { ApiError } from '@/api/client'
import { listAllNotes } from '@/api/listAll'
import { joinQueries, useQuery } from '@/api/useQuery'
import type { NoteSummary, ProjectDetail } from '@/api/types'
import { Card } from '@/components/Card'
import { EmptyState } from '@/components/EmptyState'
import { ProgressBar } from '@/components/ProgressBar'
import { QueryBoundary } from '@/components/QueryBoundary'
import { usePageTitle } from '@/components/PageTitle'
import { Segmented } from '@/components/Segmented'
import { StatTile } from '@/components/StatTile'
import { StatusChip } from '@/components/StatusChip'
import { projectHealth, projectProgress } from '@/domain/health'
import { NoteReader } from '@/features/notes/NoteReader'
import { SplitPane } from '@/features/notes/SplitPane'
import { useMinWidth, useSplitLayout } from '@/lib/viewport'
import { useToday } from '@/lib/clock'
import { NOT_AVAILABLE } from '@/lib/dates'
import { routes } from '@/lib/routes'
import { LATER_TABS, LaterTabContent, type LaterTab } from './LaterTabs'
import { DecisionsTab, NotesTab } from './NoteTabs'
import { Overview } from './Overview'
import { projectCounts } from './domain'
import { TasksTab } from './TasksTab'
import { useProjectHref } from '@/lib/projectContext'

const TABS = [
  { value: 'overview', label: 'Overview' },
  { value: 'tasks', label: 'Tasks' },
  { value: 'decisions', label: 'Decisions' },
  { value: 'notes', label: 'Notes' },
] as const
type Tab = (typeof TABS)[number]['value'] | LaterTab
const ALL_TABS: readonly string[] = [...TABS, ...LATER_TABS].map((t) => t.value)

function NotFound({ slug }: { slug: string }) {
  const href = useProjectHref()
  return (
    <Card>
      <div className="px-3 pt-3">
        <h2 className="t-panel font-semibold">Project not found</h2>
      </div>
      <EmptyState className="pt-1" action={<Link to={href.link(routes.projects)}>Back to all projects</Link>}>
        No project has the slug {slug}. It may have been renamed or deleted in Obsidian.
      </EmptyState>
    </Card>
  )
}

function Loaded({ detail, tasks, tab }: { detail: ProjectDetail; tasks: NoteSummary[]; tab: Tab }) {
  const href = useProjectHref()
  const today = useToday()
  const [params, setParams] = useSearchParams()
  const split = useSplitLayout()
  const roomy = useMinWidth(640)
  const { project } = detail
  usePageTitle(project.title)
  const health = projectHealth(project, tasks, today)
  const progress = projectProgress(tasks)
  const counts = projectCounts(tasks, today)
  const note = params.get('note') ?? undefined

  const change = (next: (q: URLSearchParams) => void) => {
    const q = new URLSearchParams(params)
    next(q)
    setParams(q)
  }
  const pick = (value: Tab) =>
    change((q) => {
      if (value === 'overview') q.delete('tab')
      else q.set('tab', value)
      q.delete('note')
    })
  const open = split ? (n: NoteSummary) => change((q) => q.set('note', n.path)) : undefined
  const reader = split && note ? <NoteReader path={note} onClose={() => change((q) => q.delete('note'))} /> : undefined

  const withReader = (list: React.ReactNode) => <SplitPane list={list} reader={reader} readerLabel="Open note" />

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h2 className="t-page min-w-0 font-bold break-words">{project.title}</h2>
          <StatusChip status={project.status} />
          <span className="flex items-center gap-2">
            <StatusChip label={health.label} tone={health.tone} />
            <span className="t-small text-muted-ink">{health.reason}</span>
          </span>
        </div>
        <p className="m-0 text-muted-ink">{project.goal ?? NOT_AVAILABLE}</p>
      </header>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile compact icon="tasks" tone="progress" value={counts.open} label="Open" to={href.tasks({ project: project.slug, status: 'open' })} />
        <StatTile compact icon="blocked" tone="blocked" value={counts.blocked} label="Blocked" to={href.tasks({ project: project.slug, status: 'blocked' })} />
        <StatTile compact icon="flag" tone="blocked" value={counts.overdue} label="Overdue" to={href.tasks({ project: project.slug, status: 'open', overdue: true })} />
        <StatTile
          compact
          icon="tasks"
          tone="done"
          value={progress.total ? `${progress.done} of ${progress.total}` : NOT_AVAILABLE}
          label="Done"
          to={href.tasks({ project: project.slug, status: 'done' })}
        />
      </div>
      <div className="flex items-center gap-3">
        <ProgressBar percent={progress.percent} label={`${project.title} progress`} />
        <span className="num t-small flex-none text-muted-ink">{progress.text}</span>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Segmented label="Project sections" options={[...TABS]} value={tab} onChange={pick} />
        <div className="flex flex-wrap items-center gap-2">
          <span className="t-small text-muted-ink">Later</span>
          <Segmented label="Later sections" options={[...LATER_TABS]} value={tab} onChange={pick} />
        </div>
      </div>

      {tab === 'overview' && <Overview detail={detail} tasks={tasks} slug={project.slug} />}
      {tab === 'tasks' && withReader(<TasksTab tasks={tasks} phone={!roomy} selectedPath={note} onOpen={open} />)}
      {tab === 'decisions' && withReader(<DecisionsTab decisions={detail.decisions} selectedPath={note} onOpen={open} />)}
      {tab === 'notes' && withReader(<NotesTab slug={project.slug} selectedPath={note} onOpen={open} />)}
      {(LATER_TABS as readonly { value: string }[]).some((t) => t.value === tab) && <LaterTabContent tab={tab as LaterTab} slug={project.slug} />}
    </div>
  )
}

/**
 * One project: header with status and health, four counts and the progress
 * bar, then tabs from the `tab` query parameter. Overview answers "what is
 * this project's state" on its own; the Later tabs show sample data.
 */
export function ProjectPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  const client = useApi()
  const [params] = useSearchParams()
  const requested = params.get('tab') ?? ''
  const tab = (ALL_TABS.includes(requested) ? requested : 'overview') as Tab

  const detail = useQuery(useCallback(() => client.getProject(slug), [client, slug]))
  const tasks = useQuery(useCallback(() => listAllNotes(client, { type: 'task', project: slug, ordering: 'path' }), [client, slug]))
  const query = useMemo(() => joinQueries(detail, tasks), [detail, tasks])

  if (detail.status === 'error' && detail.error instanceof ApiError && detail.error.status === 404) return <NotFound slug={slug} />
  return (
    <QueryBoundary query={query} rows={5}>
      {([d, t]) => <Loaded detail={d} tasks={t} tab={tab} />}
    </QueryBoundary>
  )
}

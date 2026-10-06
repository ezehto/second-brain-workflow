import { useCallback, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useApi } from '@/api/ApiProvider'
import { listAllNotes } from '@/api/listAll'
import { useQuery } from '@/api/useQuery'
import { Card, CardHead } from '@/components/Card'
import { EmptyState } from '@/components/EmptyState'
import { QueryBoundary } from '@/components/QueryBoundary'
import { Segmented } from '@/components/Segmented'
import { StatusChip } from '@/components/StatusChip'
import { projectLookup } from '@/domain/projects'
import { useToday } from '@/lib/clock'
import { formatWhen, NOT_AVAILABLE } from '@/lib/dates'
import { useProjectContext } from '@/lib/projectContext'
import { routes } from '@/lib/routes'
import { SplitPane } from '@/features/notes/SplitPane'
import { useMinWidth } from '@/features/notes/useMediaQuery'
import { filterLessons, LESSON_STATUSES, parseListParams, tagsOf } from './filters'
import { ListRow, NoteLink } from './parts'
import { useReaderPane } from './useReaderPane'

const TEMPLATE = 'minmax(0,1fr) 9rem 12rem 5rem'
const ALL = 'all'

/**
 * "What did we learn about X?" Lessons from 05-Knowledge/Lessons as dense
 * rows, newest change first. Project (the context switcher), tag and status
 * are URL parameters; a row opens the note in the split pane from 1024 up.
 */
export function KnowledgePage() {
  const client = useApi()
  const today = useToday()
  const [params] = useSearchParams()
  const project = useProjectContext()
  const view = useMemo(() => parseListParams(params, LESSON_STATUSES), [params])
  const { setParam, onOpen, reader } = useReaderPane(view)
  const roomy = useMinWidth(640)

  const lessons = useQuery(useCallback(() => listAllNotes(client, { type: 'lesson', ordering: '-modified' }), [client]))
  const projects = useQuery(useCallback(() => client.listProjects(), [client]))
  const lookup = useMemo(() => projectLookup(projects.status === 'success' ? projects.data : undefined), [projects])
  const stacked = !roomy || !!reader

  return (
    <QueryBoundary
      query={lessons}
      rows={5}
      isEmpty={(all) => all.length === 0}
      empty={<>No lessons yet. Use New in the header to add one, or add a note to 05-Knowledge/Lessons in Obsidian.</>}
    >
      {(all) => {
        const inProject = filterLessons(all, { project: project ?? undefined }, { ignoreStatus: true })
        const tags = tagsOf(inProject)
        const shown = filterLessons(all, { ...view, project: project ?? undefined })
        return (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
              <Segmented
                label="Filter by status"
                value={view.status ?? ALL}
                onChange={(s) => setParam('status', s === ALL ? undefined : s)}
                options={[{ value: ALL, label: 'All' }, ...LESSON_STATUSES.map((s) => ({ value: s as string, label: s }))]}
              />
              {tags.length > 0 && (
                <Segmented
                  label="Filter by tag"
                  value={view.tag ?? ALL}
                  onChange={(t) => setParam('tag', t === ALL ? undefined : t)}
                  options={[
                    { value: ALL, label: 'All tags' },
                    ...(view.tag && !tags.includes(view.tag) ? [view.tag] : []).concat(tags).map((t) => ({ value: t, label: t })),
                  ]}
                />
              )}
            </div>
            <SplitPane
              reader={reader}
              readerLabel="Open note"
              list={
                <Card>
                  <CardHead title="Lessons" count={shown.length} />
                  {shown.length === 0 ? (
                    <EmptyState className="border-t border-line pt-3" action={<Link to={routes.knowledge}>Clear filters</Link>}>
                      No lessons match these filters.
                    </EmptyState>
                  ) : (
                    <ul className="m-0 list-none p-0">
                      {shown.map((n) => (
                        <li key={n.path}>
                          <ListRow
                            stacked={stacked}
                            selected={n.path === view.note}
                            template={TEMPLATE}
                            title={
                              <div className="flex min-w-0 items-baseline gap-2">
                                <NoteLink note={n} onOpen={onOpen} />
                                {n.status === 'archived' && <StatusChip status="archived" />}
                              </div>
                            }
                            columns={[
                              <span key="project" className="t-small truncate text-muted-ink">{lookup.title(n.project)}</span>,
                              <span key="tags" className="t-small truncate text-muted-ink">{n.tags.join(', ') || NOT_AVAILABLE}</span>,
                              <span key="when" className="num t-caption text-muted-ink">{formatWhen(n.modified, today)}</span>,
                            ]}
                          />
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
              }
            />
          </div>
        )
      }}
    </QueryBoundary>
  )
}

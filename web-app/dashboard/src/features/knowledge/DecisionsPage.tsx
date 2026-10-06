import { useCallback, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useApi } from '@/api/ApiProvider'
import { listAllNotes } from '@/api/listAll'
import { useQuery } from '@/api/useQuery'
import { Card, CardHead } from '@/components/Card'
import { EmptyState } from '@/components/EmptyState'
import { QueryBoundary } from '@/components/QueryBoundary'
import { Segmented } from '@/components/Segmented'
import { StatusMenu } from '@/components/StatusMenu'
import { projectLookup } from '@/domain/projects'
import { formatShortDate } from '@/lib/dates'
import { useProjectContext, useProjectHref } from '@/lib/projectContext'
import { routes } from '@/lib/routes'
import { SplitPane } from '@/features/notes/SplitPane'
import { useMinWidth } from '@/lib/viewport'
import { DECISION_STATUSES, filterDecisions, groupDecisions, parseListParams } from './filters'
import { ListRow, NoteLink } from './parts'
import { useReaderPane } from './useReaderPane'

const TEMPLATE = 'minmax(0,1fr) 9rem 6rem'
const ALL = 'all'

/**
 * "What did we decide?" Decisions from 05-Knowledge/Decisions grouped by
 * status, `proposed` first because those still need an answer. The status
 * segments carry their counts and write `?status=`; each row's status is a
 * `StatusMenu`, so a decision is accepted or rejected in place.
 */
export function DecisionsPage() {
  const href = useProjectHref()
  const client = useApi()
  const [params] = useSearchParams()
  const project = useProjectContext()
  const view = useMemo(() => parseListParams(params, DECISION_STATUSES), [params])
  const { setParam, onOpen, reader } = useReaderPane(view)
  const roomy = useMinWidth(640)

  const decisions = useQuery(useCallback(() => listAllNotes(client, { type: 'decision', ordering: '-modified' }), [client]))
  const projects = useQuery(useCallback(() => client.listProjects(), [client]))
  const lookup = useMemo(() => projectLookup(projects.status === 'success' ? projects.data : undefined), [projects])
  const stacked = !roomy || !!reader

  return (
    <QueryBoundary
      query={decisions}
      rows={5}
      isEmpty={(all) => all.length === 0}
      empty={<>No decisions yet. Use New in the header to record one, or add a note to 05-Knowledge/Decisions in Obsidian.</>}
    >
      {(all) => {
        const scope = { ...view, project: project ?? undefined }
        const inProject = filterDecisions(all, scope, { ignoreStatus: true })
        const shown = filterDecisions(all, scope)
        const groups = groupDecisions(shown)
        const count = (s: string) => inProject.filter((d) => d.status === s).length
        return (
          <div className="flex flex-col gap-4">
            <Segmented
              label="Filter by status"
              value={view.status ?? ALL}
              onChange={(s) => setParam('status', s === ALL ? undefined : s)}
              options={[
                { value: ALL, label: `All ${inProject.length}` },
                ...DECISION_STATUSES.map((s) => ({ value: s as string, label: `${s} ${count(s)}` })),
              ]}
            />
            <SplitPane
              reader={reader}
              readerLabel="Open note"
              list={
                <Card>
                  <CardHead title="Decisions" count={shown.length} />
                  {groups.length === 0 ? (
                    <EmptyState className="border-t border-line pt-3" action={<Link to={href.link(routes.decisions)}>Clear filters</Link>}>
                      No decisions match these filters.
                    </EmptyState>
                  ) : (
                    groups.map((group) => (
                      <section key={group.key} aria-labelledby={`group-${group.key}`}>
                        <div className="flex min-h-8 items-center justify-between gap-3 border-t border-line bg-inset px-3">
                          <h3 id={`group-${group.key}`} className="t-small font-semibold">
                            {group.label}
                          </h3>
                          <span className="num t-caption text-muted-ink">
                            <span className="sr-only">Decisions: </span>
                            {group.decisions.length}
                          </span>
                        </div>
                        <ul className="m-0 list-none p-0">
                          {group.decisions.map((n) => (
                            <li key={n.path}>
                              <ListRow
                                stacked={stacked}
                                selected={n.path === view.note}
                                template={TEMPLATE}
                                lead={<StatusMenu note={n} />}
                                title={<NoteLink note={n} onOpen={onOpen} />}
                                columns={[
                                  <span key="project" className="t-small truncate text-muted-ink">{lookup.title(n.project)}</span>,
                                  <span key="decided" className="num t-caption text-muted-ink">
                                    <span className="sr-only">Decided </span>
                                    {formatShortDate(n.decided)}
                                  </span>,
                                ]}
                              />
                            </li>
                          ))}
                        </ul>
                      </section>
                    ))
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

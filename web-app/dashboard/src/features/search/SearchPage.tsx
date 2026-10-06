import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useApi } from '@/api/ApiProvider'
import { listAllNotes } from '@/api/listAll'
import type { NoteSummary, SearchResponse } from '@/api/types'
import { joinQueries, useQuery, type Query } from '@/api/useQuery'
import { Card, CardHead } from '@/components/Card'
import { EmptyState } from '@/components/EmptyState'
import { Icon } from '@/components/Icon'
import { QueryBoundary } from '@/components/QueryBoundary'
import { Segmented } from '@/components/Segmented'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useToday } from '@/lib/clock'
import { formatWhen } from '@/lib/dates'
import { useProjectContext, useProjectHref } from '@/lib/projectContext'
import { projectLookup } from '@/domain/projects'
import { NoteReader } from '@/features/notes/NoteReader'
import { SplitPane } from '@/features/notes/SplitPane'
import { useSplitLayout } from '@/lib/viewport'
import { ResultRow } from './ResultRow'
import { useDebouncedValue } from './useDebouncedValue'

export const SEARCH_DEBOUNCE_MS = 250
const ALL = 'all'
const RECENT_COUNT = 10

/**
 * `/search?q=`: the query lives in the URL (`q`, plus `type` and `note` for the
 * type filter and the open note), so a result list can be linked and the
 * header's search box lands here. The page's own input is debounced into `q`.
 * Results are grouped by note type; every row names its source.
 */
export function SearchPage() {
  const client = useApi()
  const today = useToday()
  const split = useSplitLayout()
  const context = useProjectContext()
  const [params, setParams] = useSearchParams()
  const urlQuery = params.get('q') ?? ''
  const type = params.get('type') ?? ALL
  const openPath = params.get('note')

  const [input, setInput] = useState(urlQuery)
  const written = useRef(urlQuery)
  const debounced = useDebouncedValue(input, SEARCH_DEBOUNCE_MS)

  // Typing -> URL, once the typing pauses. Replace, so Back is not one step per query.
  useEffect(() => {
    const next = debounced.trim()
    if (next === urlQuery.trim()) return
    written.current = next
    setParams(
      (prev) => {
        const p = new URLSearchParams(prev)
        if (next) p.set('q', next)
        else p.delete('q')
        p.delete('type')
        p.delete('note')
        return p
      },
      { replace: true },
    )
    // urlQuery is deliberately not a dependency: a URL change from elsewhere must not be written back.
  }, [debounced]) // eslint-disable-line react-hooks/exhaustive-deps

  // URL -> input, when the URL changed from elsewhere (the header's search box, Back).
  useEffect(() => {
    if (urlQuery.trim() !== written.current) {
      written.current = urlQuery.trim()
      setInput(urlQuery)
    }
  }, [urlQuery])

  const q = urlQuery.trim()
  const results = useQuery(
    useCallback((): Promise<SearchResponse> => (q ? client.search(q) : Promise.resolve({ query: '', results: [] })), [client, q]),
  )
  // Every note, for the project of each result and for the recent list: the search API does not return a project.
  const notes = useQuery(useCallback(() => listAllNotes(client, { ordering: '-modified' }), [client]))
  const projects = useQuery(useCallback(() => client.listProjects(), [client]))
  const lookup = useMemo(() => projectLookup(projects.status === 'success' ? projects.data : undefined), [projects])
  const projectOf = useMemo(() => new Map((notes.status === 'success' ? notes.data : []).map((n) => [n.path, n.project])), [notes])

  // With a project context the results are narrowed by each note's project, which only the note list knows,
  // so the boundary waits for it (and shows its error) instead of reporting "nothing matches" too early.
  const noteGate: Query<NoteSummary[]> = context ? notes : { status: 'success', data: [], error: undefined, refetch: notes.refetch }
  const gated = joinQueries(results, noteGate)

  const setParam = (key: string, value: string | null) =>
    setParams((prev) => {
      const p = new URLSearchParams(prev)
      if (value) p.set(key, value)
      else p.delete(key)
      return p
    })

  const input$ = (
    <div className="relative flex items-center">
      <label htmlFor="search-page-input" className="sr-only">
        Search the vault
      </label>
      <span className="pointer-events-none absolute left-3 flex text-muted-ink">
        <Icon name="search" className="size-4" />
      </span>
      <Input
        id="search-page-input"
        type="search"
        value={input}
        placeholder="Search titles and note text"
        className="pl-9"
        onChange={(e) => setInput(e.target.value)}
      />
    </div>
  )

  const list = (
    <div className="flex flex-col gap-4">
      {input$}
      {!q ? (
        <Recent notes={notes} context={context} today={today} lookup={lookup} />
      ) : (
        <QueryBoundary query={gated} rows={4}>
          {([data]) => {
            const inContext = data.results.filter((r) => !context || projectOf.get(r.path) === context)
            const counts = new Map<string, number>()
            inContext.forEach((r) => counts.set(r.type, (counts.get(r.type) ?? 0) + 1))
            const types = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([t]) => t)
            const active = type !== ALL && counts.has(type) ? type : ALL
            const shown = active === ALL ? inContext : inContext.filter((r) => r.type === active)
            const heading = `${inContext.length} ${inContext.length === 1 ? 'result' : 'results'} for "${q}" in the vault`

            if (inContext.length === 0) {
              return (
                <Card>
                  <CardHead title={heading} />
                  <EmptyState
                    action={
                      type !== ALL ? (
                        <Button variant="secondary" size="sm" onClick={() => setParam('type', null)}>
                          Remove the type filter
                        </Button>
                      ) : undefined
                    }
                  >
                    {context ? 'Nothing in this project matches. Switch to All projects to search every note.' : 'No notes match. Try fewer or different words.'}
                    {type !== ALL && ` The type filter is set to ${type}; removing it may show more.`}
                  </EmptyState>
                </Card>
              )
            }
            return (
              <div className="flex flex-col gap-3">
                <Segmented
                  label="Filter by note type"
                  value={active}
                  onChange={(v) => setParam('type', v === ALL ? null : v)}
                  options={[{ value: ALL, label: `All (${inContext.length})` }, ...types.map((t) => ({ value: t, label: `${t} (${counts.get(t)})` }))]}
                />
                <Card>
                  <CardHead title={heading} />
                  {shown.length === 0 ? (
                    <EmptyState>No {active} notes match.</EmptyState>
                  ) : (
                    <ul className="m-0 list-none p-0">
                      {shown.map((r) => (
                        <ResultRow
                          key={r.path}
                          result={r}
                          query={q}
                          project={projectOf.get(r.path) ? lookup.title(projectOf.get(r.path) ?? null) : null}
                          selected={split && r.path === openPath}
                          onSelect={split ? (path) => setParam('note', path) : undefined}
                        />
                      ))}
                    </ul>
                  )}
                </Card>
              </div>
            )
          }}
        </QueryBoundary>
      )}
    </div>
  )

  const reader = split && q && openPath ? <NoteReader path={openPath} onClose={() => setParam('note', null)} /> : undefined
  return <SplitPane list={list} reader={reader} />
}

function Recent({
  notes,
  context,
  today,
  lookup,
}: {
  notes: Query<NoteSummary[]>
  context: string | null
  today: string
  lookup: ReturnType<typeof projectLookup>
}) {
  const href = useProjectHref()
  return (
    <Card>
      <CardHead title="Recently modified" count={RECENT_COUNT} />
      <p className="t-body m-0 px-3 pb-2 text-muted-ink">Type above to search the vault. Until then, here are the notes that changed last.</p>
      <QueryBoundary query={notes} isEmpty={(all) => all.length === 0} empty="The vault has no notes yet.">
        {(all) => (
          <ul className="m-0 list-none p-0">
            {all
              .filter((n) => !context || n.project === context)
              .slice(0, RECENT_COUNT)
              .map((n) => (
                <li key={n.path} className="flex min-h-9 flex-wrap items-center gap-x-3 gap-y-1 border-t border-line px-3 py-2">
                  <span className="t-small rounded-full bg-inset px-2 py-px font-semibold text-muted-ink">{n.type}</span>
                  <Link to={href.note(n.path)} className="t-body min-w-0 flex-1 font-semibold text-ink underline-offset-2 hover:underline">
                    {n.title}
                  </Link>
                  <span className="t-small text-muted-ink">{n.project ? lookup.title(n.project) : null}</span>
                  <span className="t-small num text-muted-ink">{formatWhen(n.modified, today)}</span>
                </li>
              ))}
          </ul>
        )}
      </QueryBoundary>
    </Card>
  )
}

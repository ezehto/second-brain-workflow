import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { useApi, useInvalidate } from '@/api/ApiProvider'
import type { DashboardResponse, NoteSummary, ProjectSummary, StandupSection } from '@/api/types'
import type { Query } from '@/api/useQuery'
import { Card, CardHead, CardRow } from '@/components/Card'
import { QueryBoundary } from '@/components/QueryBoundary'
import { StatusChip } from '@/components/StatusChip'
import { useToast } from '@/components/Toast'
import { Button } from '@/components/ui/button'
import { parseDaily, previewSections } from '@/domain/daily'
import { summarizeStandup } from '@/domain/standup'
import { useToday } from '@/lib/clock'
import { useProjectHref } from '@/lib/projectContext'
import { plural } from '@/lib/plural'
import { routes } from '@/lib/routes'
import { AddLine } from '@/features/standup/AddLine'
import { LineRow } from '@/features/standup/LineRow'
import { linkResolver } from '@/features/standup/links'

/** The three sections the Dashboard writes to; the Standup page has all six. */
const SECTIONS: StandupSection[] = ['Done', 'Today', 'Blockers']
const SHOWN = 4

/**
 * Today's standup, writable in place: Start standup when the note is missing,
 * Fill with carry-forward when it is untouched, and an add field per section
 * through the append endpoint (using the Standup page's `AddLine` and
 * `LineRow`). The full six sections and history are on the Standup page.
 */
export function StandupPanel({
  dashboard,
  projects,
  tasks,
}: {
  dashboard: Query<DashboardResponse>
  projects: Query<ProjectSummary[]>
  tasks: Query<NoteSummary[]>
}) {
  const href = useProjectHref()
  const client = useApi()
  const invalidate = useInvalidate()
  const toast = useToast()
  const today = useToday()
  const [busy, setBusy] = useState(false)

  const standup = dashboard.status === 'success' ? dashboard.data.standup : null
  const note = standup?.exists ? standup.note : undefined
  const resolver = useMemo(
    () => linkResolver(projects.status === 'success' ? projects.data : [], tasks.status === 'success' ? tasks.data : [], note),
    [projects, tasks, note],
  )

  async function start() {
    setBusy(true)
    try {
      const result = await client.startStandup()
      toast.show(
        result.created
          ? `Created ${result.note.path} with carry-forward`
          : result.filled
            ? `Filled ${result.note.path} with carry-forward`
            : `${result.note.path} was edited by hand, left unchanged`,
      )
      invalidate()
    } catch (error) {
      toast.show(error instanceof Error ? error.message : 'The standup could not be started.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card aria-label="Standup today">
      <CardHead title="Standup today">
        <Button asChild variant="secondary" size="sm">
          <Link to={href.link(routes.standups)}>Open standup</Link>
        </Button>
      </CardHead>
      <QueryBoundary query={dashboard} rows={3}>
        {(d) => {
          const summary = summarizeStandup(d.standup, today)
          const sections = d.standup.exists ? parseDaily(d.standup.note.body) : previewSections(d.standup.preview)
          const written = d.standup.exists ? d.standup : null
          const state = !d.standup.exists ? 'Not started' : d.standup.untouched ? 'Untouched' : 'Edited by hand'
          return (
            <>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line px-3 py-2">
                <StatusChip label={state} tone={d.standup.exists && !d.standup.untouched ? 'progress' : 'neutral'} />
                <span className="mono min-w-0 break-all text-muted-ink">{summary.path}</span>
                <span className="flex-1" />
                {!d.standup.exists && (
                  <Button size="sm" onClick={start} disabled={busy}>
                    Start standup
                  </Button>
                )}
                {d.standup.exists && d.standup.untouched && (
                  <Button size="sm" onClick={start} disabled={busy}>
                    Fill with carry-forward
                  </Button>
                )}
              </div>
              {!d.standup.exists && (
                <p className="t-small m-0 border-t border-line px-3 py-2 text-muted-ink">
                  Not started. {plural(summary.today_count, 'task')} and {plural(summary.blocker_count, 'blocker')} would be carried forward.
                </p>
              )}
              {written &&
                SECTIONS.map((section) => {
                  const lines = sections[section]
                  return (
                    <section key={section} aria-label={section} className="border-t border-line">
                      <h3 className="t-small flex items-baseline gap-2 px-3 pt-2 font-semibold">
                        {section}
                        <span className="num t-numeral font-normal text-muted-ink">{lines.length}</span>
                      </h3>
                      {lines.slice(0, SHOWN).map((line, i) => (
                        <LineRow key={`${line.key}-${i}`} line={line} resolver={resolver} />
                      ))}
                      {lines.length > SHOWN && (
                        <CardRow className="min-h-8">
                          <Link to={href.link(routes.standups)} className="t-small">
                            {lines.length - SHOWN} more in the standup
                          </Link>
                        </CardRow>
                      )}
                      {lines.length === 0 && (
                        <p className="t-small m-0 border-t border-line px-3 py-2 text-muted-ink">Nothing here yet.</p>
                      )}
                      <AddLine section={section} note={written.note} untouched={written.untouched} />
                    </section>
                  )
                })}
            </>
          )
        }}
      </QueryBoundary>
    </Card>
  )
}

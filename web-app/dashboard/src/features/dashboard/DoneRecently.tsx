import { Link } from 'react-router'
import { useCallback } from 'react'
import { useApi } from '@/api/ApiProvider'
import { useQuery, type Query } from '@/api/useQuery'
import type { NoteSummary } from '@/api/types'
import { Card, CardHead, CardRow } from '@/components/Card'
import { QueryBoundary } from '@/components/QueryBoundary'
import { doneByDay, doneRecently, type DayCount } from '@/domain/dashboard'
import { evidenceLine } from '@/domain/evidence'
import { useToday } from '@/lib/clock'
import { useProjectHref } from '@/lib/projectContext'
import { formatShortDate } from '@/lib/dates'

const WEEKDAY = new Intl.DateTimeFormat('en-GB', { weekday: 'short', timeZone: 'UTC' })
const BAR_MAX_PX = 48

/** Done per day over the last 7 days (chart 2): the number is text, the bar is the hue of "done". */
export function DoneBars({ days }: { days: DayCount[] }) {
  const max = Math.max(1, ...days.map((d) => d.count))
  const total = days.reduce((n, d) => n + d.count, 0)
  return (
    <figure className="m-0 flex flex-col gap-1 px-3 py-2">
      <figcaption className="t-small text-muted-ink">How much did I finish each day? {total} in 7 days, approximate.</figcaption>
      <ol
        className="m-0 grid list-none grid-cols-7 gap-2 p-0"
        aria-label={`Tasks done per day: ${days.map((d) => `${formatShortDate(d.date)} ${d.count}`).join(', ')}`}
      >
        {days.map((d) => (
          <li key={d.date} className="flex flex-col items-center justify-end gap-0.5" style={{ height: BAR_MAX_PX + 36 }} title={`${formatShortDate(d.date)}: ${d.count} done`}>
            <span className="num t-numeral text-muted-ink">{d.count}</span>
            <span
              aria-hidden="true"
              className={d.count ? 'w-full max-w-8 rounded-t-lg bg-status-done' : 'w-full max-w-8 border-b border-line'}
              style={{ height: d.count ? Math.max(4, Math.round((d.count / max) * BAR_MAX_PX)) : 1 }}
            />
            <span className="t-caption text-muted-ink">{WEEKDAY.format(new Date(`${d.date}T00:00:00Z`))}</span>
          </li>
        ))}
      </ol>
    </figure>
  )
}

/** The first evidence line of each given done task, by path. Empty until read. */
function useEvidence(paths: string[]): Query<Record<string, string | null>> {
  const client = useApi()
  const key = paths.join('\n')
  return useQuery(
    useCallback(async () => {
      const wanted = key ? key.split('\n') : []
      const notes = await Promise.all(wanted.map((path) => client.lookupNote({ path })))
      return Object.fromEntries(notes.map((n) => [n.path, evidenceLine(n.body)]))
    }, [client, key]),
  )
}

/**
 * Tasks done in the last 7 days with their evidence line, and a bar per day.
 * Only the note's modified time is stored, so the day is approximate.
 */
export function DoneRecently({ tasks }: { tasks: Query<NoteSummary[]> }) {
  const href = useProjectHref()
  const today = useToday()
  const done = tasks.status === 'success' ? doneRecently(tasks.data, today) : []
  const evidence = useEvidence(done.map((t) => t.path))
  return (
    <Card aria-label="Done recently">
      <CardHead title="Done recently" count={tasks.status === 'success' ? done.length : undefined} note="Approximate, by last change" />
      <QueryBoundary query={tasks} rows={2} isEmpty={() => done.length === 0} empty="Nothing finished in the last 7 days.">
        {() => (
          <>
            {done.map((t) => (
              <CardRow key={t.path} lines={2} className="grid-cols-[minmax(0,1fr)_auto] py-1.5">
                <div className="flex min-w-0 flex-col">
                  <Link to={href.note(t.path)} className="linkbtn t-body truncate">
                    {t.title}
                  </Link>
                  <span className="t-small truncate text-muted-ink">
                    {evidence.status === 'success' ? (evidence.data[t.path] ?? 'No evidence recorded.') : evidence.status === 'error' ? 'Evidence could not be loaded.' : ' '}
                  </span>
                </div>
                <span className="num t-caption text-muted-ink">{formatShortDate(t.modified)}</span>
              </CardRow>
            ))}
            <div className="border-t border-line">
              <DoneBars days={doneByDay(done, today)} />
            </div>
          </>
        )}
      </QueryBoundary>
    </Card>
  )
}

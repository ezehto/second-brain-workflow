import { Fragment, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Card, CardFootnote, CardHead, CardRow } from '@/components/Card'
import { Segmented } from '@/components/Segmented'
import { StatTile } from '@/components/StatTile'
import { StatusChip } from '@/components/StatusChip'
import { useToast } from '@/components/Toast'
import { Button } from '@/components/ui/button'
import { formatDayTitle, formatShortDate } from '@/lib/dates'
import { noteHref, routes, tasksHref } from '@/lib/routes'
import { cn } from '@/lib/utils'
import { PREVIEW_PROJECTS, previewTimeline, type PreviewTimelineEvent } from '@/preview'
import { LabelledSelect, PreviewBanner } from './controls'
import {
  CHART,
  DEFAULT_FILTERS,
  RANGES,
  SOURCE_COLOR,
  SOURCE_ORDER,
  STATUS_TONE,
  STATUS_WORD,
  actionsFor,
  applyFilters,
  dailyCounts,
  inRange,
  stackedPaths,
  type TimelineFilters,
} from './timeline'

const { events, asOf, eventTypes, sourceLabels, trails, suggestion, source } = previewTimeline
const PROJECT_OPTIONS = [
  { value: 'all', label: 'All' },
  ...Object.entries(PREVIEW_PROJECTS).map(([value, label]) => ({
    value,
    label,
  })),
]
const SOURCE_OPTIONS = [{ value: 'all', label: 'All' }, ...SOURCE_ORDER.map((value) => ({ value, label: sourceLabels[value] }))]
const RANGE_OPTIONS = RANGES.map(({ value, label }) => ({ value, label }))
const EXTERNAL = new Set(['jira', 'gitlab', 'calendar'])

const eventTitle = (e: PreviewTimelineEvent) => (e.ref && e.source !== 'vault' && e.type !== 'deploy' ? `${e.ref} ${e.title}` : e.title)
const phaseOf = (e: PreviewTimelineEvent) =>
  EXTERNAL.has(e.source) ? 'Phase 4' : e.type === 'document' ? 'Phase 2' : e.type === 'learning' ? 'Phase 3' : 'Phase 1'
const projectText = (e: PreviewTimelineEvent) => e.projects.map((p) => PREVIEW_PROJECTS[p]).join(', ')

/** Phase 4 preview: what changed, in order, across the vault and the tools that will be connected. */
export function TimelinePage() {
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const filters: TimelineFilters = {
    range: params.get('range') ?? DEFAULT_FILTERS.range,
    project: params.get('project') ?? DEFAULT_FILTERS.project,
    source: params.get('source') ?? DEFAULT_FILTERS.source,
    type: params.get('type') ?? DEFAULT_FILTERS.type,
  }
  const [selectedId, setSelectedId] = useState(previewTimeline.selectedId)
  const [link, setLink] = useState<'pending' | 'linked' | 'dismissed'>('pending')

  const setFilter = (key: keyof TimelineFilters, value: string) => {
    const next = new URLSearchParams(params)
    if (value === DEFAULT_FILTERS[key]) next.delete(key)
    else next.set(key, value)
    setParams(next, { replace: true })
  }
  const filtered = !(Object.keys(DEFAULT_FILTERS) as (keyof TimelineFilters)[]).every((k) => filters[k] === DEFAULT_FILTERS[k])
  const reset = () => setParams(new URLSearchParams(), { replace: true })

  const shown = applyFilters(events, filters, asOf)
  const rangeEvents = inRange(events, filters.range, asOf)
  const count = (type: string) => rangeEvents.filter((e) => e.type === type).length
  const q = (type: string) => `${routes.timeline}?type=${type}`

  const dates = [...new Set(shown.map((e) => e.date))].sort().reverse()
  const selected = events.find((e) => e.id === selectedId) ?? events[0]

  return (
    <div className="flex flex-col gap-4">
      <PreviewBanner phase="Phase 4" what="Jira, GitLab and Calendar events arrive when those integrations are connected." source={source} />

      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(200px,100%),1fr))] gap-4">
        <StatTile compact icon="tasks" tone="done" value={count('task-completed')} label="Tasks completed" to={tasksHref({ status: 'done' })} />
        <StatTile compact icon="decisions" tone="review" value={count('decision')} label="Decisions recorded" to={routes.decisions} />
        <StatTile compact icon="branch" tone="progress" value={count('deploy')} label="Deployments" to={q('deploy')} />
        <StatTile compact icon="alert" tone="blocked" value={count('incident')} label="Incidents" to={q('incident')} />
      </div>

      <EventsChart range={filters.range} />

      {/* Sticky under the top bar (52px, 48px on a phone) so the filters stay in reach while the list grows with the page. */}
      <Card className="sticky top-12 z-20 sm:top-[52px]">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-1">
          <Segmented label="Range" options={RANGE_OPTIONS} value={filters.range} onChange={(v) => setFilter('range', v)} />
          <Segmented label="Project" options={PROJECT_OPTIONS} value={filters.project} onChange={(v) => setFilter('project', v)} />
          <Segmented label="Source" options={SOURCE_OPTIONS} value={filters.source} onChange={(v) => setFilter('source', v)} />
          <LabelledSelect id="tl-type" label="Type" value={filters.type} onChange={(e) => setFilter('type', e.target.value)}>
            <option value="all">All types</option>
            {Object.entries(eventTypes).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </LabelledSelect>
          <span className="t-small ml-auto text-muted-ink" role="status">
            Showing {shown.length} of {events.length} events
          </span>
          <Button type="button" size="sm" variant="ghost" onClick={reset} disabled={!filtered}>
            Reset filters
          </Button>
        </div>
      </Card>

      <div className="flex flex-wrap items-start gap-4">
        <Card className="flex-[7_1_520px]">
          <CardHead title="What changed" count={shown.length} />
          {shown.length === 0 && (
            <div className="flex flex-col items-start gap-2 px-3 pb-3 text-muted-ink">
              <p className="m-0">No events match these filters. Widen the range or reset the filters.</p>
              <Button type="button" size="sm" variant="secondary" onClick={reset}>
                Reset filters
              </Button>
            </div>
          )}
          <div role="region" aria-label="Events by day">
            {dates.map((date) => {
              const dayEvents = shown.filter((e) => e.date === date).sort((a, b) => b.time.localeCompare(a.time))
              return (
                <section key={date} aria-label={formatDayTitle(date)}>
                  <div className="flex min-h-9 items-baseline gap-2 border-t border-line bg-inset px-3 py-1">
                    <h3 className="t-body font-semibold">
                      {formatDayTitle(date)}
                      {date === asOf ? ', today' : ''}
                    </h3>
                    <span className="num t-caption text-muted-ink">{dayEvents.length === 1 ? '1 event' : `${dayEvents.length} events`}</span>
                  </div>
                  {dayEvents.map((e, i) => (
                    <EventRow
                      key={e.id}
                      e={e}
                      last={i === dayEvents.length - 1}
                      selected={e.id === selected.id}
                      link={link}
                      onSelect={() => setSelectedId(e.id)}
                    />
                  ))}
                </section>
              )
            })}
          </div>
        </Card>

        <div className="flex min-w-0 flex-[5_1_380px] flex-col gap-4">
          <Detail e={selected} onAction={(verb, file) => toast.show(`Would ${verb} ${file}`)} />
          <Trails
            link={link}
            onLink={() => {
              setLink('linked')
              toast.show(`Would add [[Settlement file rerun review]] under Related in ${suggestion.file}`)
            }}
            onDismiss={() => {
              setLink('dismissed')
              toast.show('Dismissed. No file written.')
            }}
          />
        </div>
      </div>
    </div>
  )
}

function EventsChart({ range }: { range: string }) {
  const days = useMemo(() => dailyCounts(events, range, asOf), [range])
  const paths = useMemo(() => stackedPaths(days), [days])
  const n = days.length
  const step = Math.ceil(n / 8)
  const total = days.reduce((a, d) => a + d.total, 0)
  const summary = `Events per day: ${days.map((d) => `${formatShortDate(d.date)} ${d.total}`).join(', ')}.`
  return (
    <Card>
      <CardHead title="How busy was each day?" count={`${total} events`}>
        <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0">
          {SOURCE_ORDER.map((s) => (
            <li key={s} className="t-small flex items-center gap-1.5">
              <span aria-hidden="true" className="size-2 rounded-full" style={{ background: SOURCE_COLOR[s] }} />
              {sourceLabels[s]}
              <span className="num text-muted-ink">{days.reduce((a, d) => a + d.bySource[s], 0)}</span>
            </li>
          ))}
        </ul>
      </CardHead>
      {n < 2 ? (
        <p className="t-small m-0 px-3 pb-3 text-muted-ink">One day in this range: {total} events. Pick 7 or 30 days to see the shape.</p>
      ) : (
        <div className="px-3 pb-3">
          <svg
            role="img"
            aria-label={summary}
            viewBox={`0 0 ${CHART.width} ${CHART.height}`}
            preserveAspectRatio="none"
            className="block h-[120px] w-full"
          >
            {paths.map(({ source: s, d }) => (
              <path
                key={s}
                d={d}
                fill={SOURCE_COLOR[s]}
                fillOpacity="0.7"
                stroke={SOURCE_COLOR[s]}
                strokeWidth="1"
                vectorEffect="non-scaling-stroke"
              />
            ))}
          </svg>
          <div aria-hidden="true" className="grid" style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }}>
            {days.map((d, i) => (
              <span key={d.date} className="t-caption flex flex-col items-center text-muted-ink">
                <span className="num t-numeral font-semibold text-ink">{n <= 10 ? d.total : ''}</span>
                <span>{i % step === 0 || i === n - 1 ? formatShortDate(d.date) : ''}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}

function EventRow({
  e,
  last,
  selected,
  link,
  onSelect,
}: {
  e: PreviewTimelineEvent
  last: boolean
  selected: boolean
  link: string
  onSelect: () => void
}) {
  const hasTrail = !!e.trail && trails[e.trail].anchorType === e.type
  const marker = hasTrail ? 'Linked trail' : e.suggestion && link === 'pending' ? 'Possible link' : e.suggestion && link === 'linked' ? 'Linked' : ''
  return (
    <CardRow lines={2} className={cn('p-0', selected && 'bg-inset')}>
      <button
        type="button"
        aria-pressed={selected}
        onClick={onSelect}
        className="grid w-full cursor-pointer grid-cols-[56px_16px_minmax(0,1fr)_auto] items-stretch gap-x-2 border-0 bg-transparent px-3 text-left text-ink hover:bg-inset"
      >
        <span className="num t-caption self-center text-muted-ink">{e.time}</span>
        <span aria-hidden="true" className="relative flex justify-center">
          <span className={cn('absolute left-1/2 w-px -translate-x-1/2 bg-line', last ? 'top-0 h-1/2' : 'inset-y-0')} />
          <span
            className="relative z-10 my-auto size-2 rounded-full border-2 border-ink bg-surface"
            style={{ borderColor: SOURCE_COLOR[e.source] }}
          />
        </span>
        <span className="flex min-w-0 flex-col justify-center py-1">
          <span className="t-body truncate font-medium">{eventTitle(e)}</span>
          <span className="t-small truncate text-muted-ink">
            {eventTypes[e.type]} · {projectText(e)} · {sourceLabels[e.source]}
          </span>
        </span>
        <span className="t-small flex flex-col items-end justify-center text-muted-ink max-sm:hidden">
          <StatusChip tone={STATUS_TONE[e.status]} label={STATUS_WORD[e.status]} />
          {marker && <span className="font-semibold text-brand">{marker}</span>}
        </span>
      </button>
    </CardRow>
  )
}

function Detail({ e, onAction }: { e: PreviewTimelineEvent; onAction: (verb: string, file: string) => void }) {
  const external = EXTERNAL.has(e.source)
  const note = e.note ?? (external ? '' : 'Time is the file modification time.')
  return (
    <Card aria-label="Selected event">
      <CardHead title="Event detail" count={eventTypes[e.type]} />
      <div className="flex flex-col gap-1 border-t border-line px-3 py-2">
        <p className="t-body m-0 font-semibold">{eventTitle(e)}</p>
        <p className="t-small m-0 text-muted-ink">
          {formatDayTitle(e.date)}, {e.time} Manila · {projectText(e)} · {sourceLabels[e.source]} · {phaseOf(e)}
        </p>
        <p className="t-small m-0">
          <StatusChip tone={STATUS_TONE[e.status]} label={STATUS_WORD[e.status]} />
        </p>
        {note && <p className="t-small m-0">{note}</p>}
        {e.quote && (
          <blockquote className="t-small m-0 border-l-2 border-line pl-3 text-muted-ink">
            {e.quote}
            <span className="t-caption block">Quoted from {sourceLabels[e.source]}. Shown as text, never acted on.</span>
          </blockquote>
        )}
        {e.file && (
          <p className="t-small m-0">
            <Link to={noteHref(e.file)} className="break-all">
              {e.file}
            </Link>
          </p>
        )}
      </div>
      <div className="flex flex-wrap gap-2 border-t border-line px-3 py-2">
        {actionsFor(e).map((a) => (
          <Button key={a.label} type="button" size="sm" variant="secondary" onClick={() => onAction(a.verb, a.file)}>
            {a.label}
          </Button>
        ))}
      </div>
      <CardFootnote>Actions write one Markdown file each; this preview names the file and writes nothing.</CardFootnote>
    </Card>
  )
}

function Trails({ link, onLink, onDismiss }: { link: 'pending' | 'linked' | 'dismissed'; onLink: () => void; onDismiss: () => void }) {
  return (
    <Card>
      <CardHead title="Linked trails" count="2 confirmed, 1 suggested" />
      {Object.entries(trails).map(([key, t]) => (
        <div key={key} className="flex flex-col gap-1 border-t border-line px-3 py-2">
          <ol className="m-0 flex list-none flex-wrap items-center gap-x-1 gap-y-1 p-0">
            {t.steps.map((s, i) => (
              <Fragment key={s.label}>
                <li className={cn('t-small rounded-btn border px-2 py-0.5', s.pending ? 'border-dashed border-line text-muted-ink' : 'border-line')}>
                  <span className="text-muted-ink">{s.label} </span>
                  <span className="font-semibold">{s.value}</span>
                  {s.note && <span className="t-caption text-muted-ink"> {s.note}</span>}
                </li>
                {i < t.steps.length - 1 && (
                  <span aria-hidden="true" className="text-muted-ink">
                    →
                  </span>
                )}
              </Fragment>
            ))}
          </ol>
          <p className="t-caption m-0 text-muted-ink">{t.basis}</p>
        </div>
      ))}
      <div className="flex flex-col gap-1 border-t border-line px-3 py-2">
        <p className="t-small m-0 font-semibold">Suggested link, not confirmed</p>
        <p className="t-small m-0">{suggestion.text}</p>
        <p className="t-caption m-0 text-muted-ink">{suggestion.basis}</p>
        {link === 'pending' ? (
          <div className="flex gap-2">
            <Button type="button" size="sm" onClick={onLink}>
              Link
            </Button>
            <Button type="button" size="sm" variant="secondary" onClick={onDismiss}>
              Dismiss
            </Button>
          </div>
        ) : (
          <p className="t-small m-0 font-semibold text-status-done">{link === 'linked' ? 'Linked.' : 'Dismissed.'}</p>
        )}
      </div>
    </Card>
  )
}

import { useId, useState } from 'react'
import { useApi, useInvalidate } from '@/api/ApiProvider'
import { STANDUP_SECTIONS, type NoteDetail, type StandupSection } from '@/api/types'
import { Card, CardHead, CardRow } from '@/components/Card'
import { PreviewBadge } from '@/components/PreviewBadge'
import { StatusChip } from '@/components/StatusChip'
import { useToast } from '@/components/Toast'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { standupAsText, type DailyDay, type DailySections, type Run } from '@/domain/daily'
import { formatDayTitle, formatShortDate } from '@/lib/dates'
import { previewStandupReferences } from '@/preview'
import { AddLine } from './AddLine'
import { LineRow } from './LineRow'
import type { LinkResolver } from './links'

export type DayState = 'missing' | 'untouched' | 'touched' | 'past'

/** One standup on screen: today's note (or its carry-forward preview) or a past note. */
export interface StandupView {
  date: string
  path: string
  sections: DailySections
  /** The note as read; null while today's note does not exist. */
  note: NoteDetail | null
  state: DayState
}

const STATE_CHIP = {
  missing: { label: 'Not started', tone: 'neutral' },
  untouched: { label: 'Untouched', tone: 'neutral' },
  touched: { label: 'Edited by hand', tone: 'progress' },
  past: { label: 'Read-only, past note', tone: 'cancelled' },
} as const

const NOTICE: Record<DayState, string> = {
  missing: 'Below is what carry-forward would write from your tasks and the previous note. Nothing is written until you start the standup.',
  untouched: 'This note is still the empty template. Fill it with carry-forward, or start typing in any section.',
  touched: 'Edited by hand, so it is shown as written. Carry-forward will not change it.',
  past: 'A past note. It cannot be changed here.',
}

function StatusCard({ view, onBack, onText, textOpen }: { view: StandupView; onBack?: () => void; onText: () => void; textOpen: boolean }) {
  const client = useApi()
  const invalidate = useInvalidate()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const chip = STATE_CHIP[view.state]

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
    <Card>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-3 py-3">
        <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h2 className="t-panel font-semibold">{formatDayTitle(view.date)}</h2>
            <StatusChip label={chip.label} tone={chip.tone} />
            <span className="mono break-all">{view.path}</span>
          </div>
          <p className="t-small m-0 text-muted-ink">{NOTICE[view.state]}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {view.state === 'missing' && (
            <Button onClick={start} disabled={busy}>
              Start standup
            </Button>
          )}
          {view.state === 'untouched' && (
            <Button onClick={start} disabled={busy}>
              Fill with carry-forward
            </Button>
          )}
          <Button variant="secondary" aria-expanded={textOpen} onClick={onText}>
            Copy as text
          </Button>
          {onBack && (
            <Button variant="outline" onClick={onBack}>
              Back to today
            </Button>
          )}
        </div>
      </div>
    </Card>
  )
}

function PlainText({ text, onClose }: { text: string; onClose: () => void }) {
  const id = useId()
  return (
    <Card>
      <CardHead title="Standup as plain text">
        <Button variant="ghost" size="sm" onClick={onClose}>
          Close
        </Button>
      </CardHead>
      <div className="flex flex-col gap-2 px-3 pb-3">
        <label htmlFor={id} className="t-small text-muted-ink">
          Ready to paste into chat. Select all, then copy.
        </label>
        <Textarea id={id} readOnly value={text} rows={14} className="mono w-full" onFocus={(e) => e.currentTarget.select()} />
      </div>
    </Card>
  )
}

function YesterdayDone({ yesterday, resolver }: { yesterday: DailyDay | null; resolver: LinkResolver }) {
  if (!yesterday) return null
  const lines = yesterday.sections.Done
  return (
    <div className="bg-inset/40">
      <div className="flex flex-wrap items-baseline gap-x-3 px-3 pt-2">
        <h3 className="t-small font-semibold">Yesterday, {formatShortDate(yesterday.date)}</h3>
        <span className="t-caption text-muted-ink">
          Read-only view of Done in <span className="mono">{yesterday.path}</span>
        </span>
      </div>
      {lines.length === 0 ? (
        <p className="t-small m-0 px-3 py-2 text-muted-ink">Nothing was listed under Done on {formatShortDate(yesterday.date)}.</p>
      ) : (
        lines.map((line, i) => <LineRow key={`${line.key}-${i}`} line={line} resolver={resolver} byTitle />)
      )}
      <h3 className="t-small border-t border-line px-3 pt-2 font-semibold">Done today</h3>
    </div>
  )
}

const EMPTY: Record<StandupSection, string> = {
  Done: 'Nothing done yet today.',
  Today: 'Nothing planned.',
  Blockers: 'Nothing is blocked.',
  'Decisions / Updates': 'No decisions or updates.',
  'Follow-ups': 'No follow-ups.',
  'Related Tasks / Projects': 'No related tasks or projects.',
}

/** The head of an empty section: one row with its title and, once the standup is started, the button that reveals the add-a-line form. */
function EmptyHead({ section, expandable, open, panelId, onToggle }: { section: StandupSection; expandable: boolean; open: boolean; panelId: string; onToggle: () => void }) {
  return (
    <div className="flex min-h-10 flex-wrap items-center gap-x-3 gap-y-1 px-3 py-1">
      <h2 className="t-panel font-semibold">{section}</h2>
      <span className="t-small text-muted-ink">{EMPTY[section]}</span>
      {expandable && (
        <Button variant="ghost" size="sm" className="ml-auto" aria-expanded={open} aria-controls={open ? panelId : undefined} onClick={onToggle}>
          Add line
        </Button>
      )}
    </div>
  )
}

function References() {
  return (
    <div className="border-t border-line">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2">
        <h3 className="t-small font-semibold">Tickets and meetings</h3>
        <PreviewBadge detail={previewStandupReferences.source} />
      </div>
      {previewStandupReferences.items.map((item) => (
        <CardRow key={item.ref} className="grid-cols-[4rem_minmax(0,1fr)_auto]">
          <span className="mono">{item.ref}</span>
          <span className="t-body min-w-0">{item.text}</span>
          <span className="t-caption text-muted-ink">{item.kind === 'ticket' ? 'Ticket' : 'Meeting'}</span>
        </CardRow>
      ))}
    </div>
  )
}

/**
 * The six sections of one standup, in the vault's heading order, with the
 * status bar above. Adding is possible only on a note that exists and is not a
 * past one.
 */
export function DayPanel({
  view,
  yesterday,
  todayRuns,
  resolver,
  onBack,
}: {
  view: StandupView
  yesterday: DailyDay | null
  /** Runs of today's Today lines across standups, for the carried-over mark. */
  todayRuns: Run[]
  resolver: LinkResolver
  onBack?: () => void
}) {
  const [textOpen, setTextOpen] = useState(false)
  const [expanded, setExpanded] = useState<ReadonlySet<StandupSection>>(new Set())
  const baseId = useId()
  const toggle = (section: StandupSection) =>
    setExpanded((was) => {
      const next = new Set(was)
      if (!next.delete(section)) next.add(section)
      return next
    })
  const runOf = new Map(todayRuns.map((r) => [r.key, r.standups]))
  const canAdd = view.state === 'untouched' || view.state === 'touched'

  return (
    <>
      <StatusCard view={view} onBack={onBack} onText={() => setTextOpen((o) => !o)} textOpen={textOpen} />
      {textOpen && <PlainText text={standupAsText({ date: view.date, yesterday, sections: view.sections })} onClose={() => setTextOpen(false)} />}
      {STANDUP_SECTIONS.map((section) => {
        const lines = view.sections[section]
        const extras = view.state !== 'past' && ((section === 'Done' && yesterday !== null) || section === 'Related Tasks / Projects')
        const collapsed = lines.length === 0 && !extras
        const addable = canAdd && view.note !== null
        const panelId = `${baseId}-section-${STANDUP_SECTIONS.indexOf(section)}`
        // One AddLine at one position in every branch, so adding the first line to a collapsed section keeps its focus and its draft.
        return (
          <Card key={section} aria-label={section}>
            {collapsed ? (
              <EmptyHead section={section} expandable={addable} open={expanded.has(section)} panelId={panelId} onToggle={() => toggle(section)} />
            ) : (
              <CardHead title={section} count={lines.length} />
            )}
            {!collapsed && section === 'Done' && view.state !== 'past' && <YesterdayDone yesterday={yesterday} resolver={resolver} />}
            {!collapsed &&
              (lines.length === 0 ? (
                <CardRow>
                  <span className="t-small text-muted-ink">{EMPTY[section]}</span>
                </CardRow>
              ) : (
                lines.map((line, i) => (
                  <LineRow key={`${line.key}-${i}`} line={line} resolver={resolver} carried={section === 'Today' && view.state !== 'past' ? runOf.get(line.key) : undefined} />
                ))
              ))}
            {!collapsed && section === 'Related Tasks / Projects' && view.state !== 'past' && <References />}
            {addable && (!collapsed || expanded.has(section)) && (
              <div id={panelId}>
                <AddLine section={section} note={view.note!} untouched={view.state === 'untouched'} />
              </div>
            )}
          </Card>
        )
      })}
    </>
  )
}

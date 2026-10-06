import type { NoteSummary, ProjectDetail } from '@/api/types'
import { Card, CardHead } from '@/components/Card'
import { Donut } from '@/components/Donut'
import { PreviewBadge } from '@/components/PreviewBadge'
import { StatusMenu } from '@/components/StatusMenu'
import { TaskRow } from '@/components/TaskRow'
import { focusOrdered } from '@/domain/focus'
import { TASK_SEGMENT_COLOR, TONE_TEXT } from '@/domain/status'
import { countByStatus, countUnknownStatus, isOpen } from '@/domain/tasks'
import { useToday } from '@/lib/clock'
import { NOT_AVAILABLE, daysBetween, formatShortDate, formatWhen } from '@/lib/dates'
import { plural } from '@/lib/plural'
import { cn } from '@/lib/utils'
import { previewProjectData } from '@/preview'
import { NoteRow } from './NoteRow'

const NEXT_LIMIT = 5

const Empty = ({ children }: { children: string }) => <p className="m-0 border-t border-line px-3 py-3 text-muted-ink">{children}</p>

function Blockers({ blocked }: { blocked: NoteSummary[] }) {
  return (
    <Card>
      <CardHead title="What is blocked, and on what?" count={blocked.length} />
      {blocked.length === 0 ? (
        <Empty>Nothing is blocked.</Empty>
      ) : (
        <ul className="m-0 list-none p-0">
          {blocked.map((t) => (
            <li key={t.path}>
              <TaskRow task={t} reason={`Blocked: ${t.blocked_by ?? NOT_AVAILABLE}`} status={<StatusMenu note={t} />} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function NextTasks({ next }: { next: NoteSummary[] }) {
  return (
    <Card>
      <CardHead title="Next tasks" count={next.length} />
      {next.length === 0 ? (
        <Empty>No open tasks. Use New in the header to add one.</Empty>
      ) : (
        <ul className="m-0 list-none p-0">
          {next.map((t) => (
            <li key={t.path}>
              <TaskRow task={t} status={<StatusMenu note={t} />} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function ProposedDecisions({ decisions }: { decisions: NoteSummary[] }) {
  const proposed = decisions.filter((d) => d.status === 'proposed')
  return (
    <Card>
      <CardHead title="Proposed decisions" count={proposed.length} />
      {proposed.length === 0 ? (
        <Empty>No decisions are waiting for approval.</Empty>
      ) : (
        <ul className="m-0 list-none p-0">
          {proposed.map((d) => (
            <li key={d.path}>
              <NoteRow note={d} status={<StatusMenu note={d} />} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function RecentNotes({ notes }: { notes: NoteSummary[] }) {
  const today = useToday()
  return (
    <Card>
      <CardHead title="Recent notes" count={notes.length} />
      {notes.length === 0 ? (
        <Empty>No notes mention this project yet.</Empty>
      ) : (
        <ul className="m-0 list-none p-0">
          {notes.map((n) => (
            <li key={n.path}>
              <NoteRow note={n} meta={`${n.type}, ${formatWhen(n.modified, today)}`} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

/** How many tasks are in each status? The counts are text beside the ring. */
function StatusDonut({ tasks }: { tasks: NoteSummary[] }) {
  const unknown = countUnknownStatus(tasks)
  const counted = tasks.length - unknown
  return (
    <Card>
      <CardHead title="How many tasks are in each status?" count={counted} />
      {tasks.length === 0 ? (
        <Empty>No tasks to count.</Empty>
      ) : (
        <>
          <Donut
            size={120}
            segments={countByStatus(tasks).map((s) => ({ label: s.status, count: s.count, color: TASK_SEGMENT_COLOR[s.status] }))}
            total={counted}
            centerLabel="tasks"
            ariaLabel={`Project tasks by status, ${counted} task notes`}
          />
          {unknown > 0 && <p className="note m-0 px-3 pb-3">{plural(unknown, 'task')} with a status outside the vocabulary not counted.</p>}
        </>
      )}
    </Card>
  )
}

const MILESTONE_TONE = { due: 'progress', blocked: 'blocked', estimated: 'neutral' } as const
const MILESTONE_WORD = { due: 'Task due date', blocked: 'Blocked', estimated: 'Estimated' } as const

function relativeDay(date: string, today: string): string {
  const d = daysBetween(today, date)
  if (d === 0) return 'today'
  return d > 0 ? `in ${plural(d, 'day')}` : `${plural(-d, 'day')} ago`
}

/** What is due soon? A short horizontal line of dated milestones, sample data. */
function Milestones({ slug }: { slug: string }) {
  const today = useToday()
  const items = [...(previewProjectData.bySlug[slug]?.milestones ?? [])].sort((a, b) => a.date.localeCompare(b.date))
  return (
    <Card>
      <CardHead title="What is due soon?" count={items.length}>
        <PreviewBadge detail={previewProjectData.source} />
      </CardHead>
      {items.length === 0 ? (
        <Empty>No milestones for this project yet.</Empty>
      ) : (
        <div className="overflow-x-auto border-t border-line px-3 py-3">
          <ol className="m-0 flex min-w-max list-none gap-6 p-0">
            {items.map((m) => (
              <li key={m.title} className="relative flex w-44 flex-col gap-1 border-t-2 border-line pt-3">
                <span aria-hidden="true" className={cn('absolute -top-[7px] left-0 size-3 rounded-full bg-current', TONE_TEXT[MILESTONE_TONE[m.state]], m.state === 'estimated' && 'bg-surface ring-2 ring-current')} />
                <span className="t-body">{m.title}</span>
                <span className="num t-small text-muted-ink">
                  {formatShortDate(m.date)}, {relativeDay(m.date, today)}
                </span>
                <span className={cn('t-small font-semibold', TONE_TEXT[MILESTONE_TONE[m.state]])}>{MILESTONE_WORD[m.state]}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </Card>
  )
}

/** Understand the project without searching: blockers and next tasks, decisions and notes, status and milestones. */
export function Overview({ detail, tasks, slug }: { detail: ProjectDetail; tasks: NoteSummary[]; slug: string }) {
  const today = useToday()
  const open = focusOrdered(tasks, today)
  const blocked = open.filter((t) => t.status === 'blocked')
  const next = open.filter((t) => t.status !== 'blocked' && isOpen(t)).slice(0, NEXT_LIMIT)
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-4">
          <Blockers blocked={blocked} />
          <NextTasks next={next} />
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          <ProposedDecisions decisions={detail.decisions} />
          <RecentNotes notes={detail.recent_notes} />
        </div>
      </div>
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <StatusDonut tasks={tasks} />
        <Milestones slug={slug} />
      </div>
    </div>
  )
}

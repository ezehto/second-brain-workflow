import type { NoteSummary } from '@/api/types'
import { Card, CardHead, CardRow } from '@/components/Card'
import { EmptyState } from '@/components/EmptyState'
import { dateOfDailyPath, type DailyDay } from '@/domain/daily'
import { formatDayTitle } from '@/lib/dates'
import { cn } from '@/lib/utils'

/**
 * Daily notes, newest first. Today is always the first row (started or not);
 * choosing a past note opens it read-only on the left.
 */
export function HistoryList({
  list,
  days,
  today,
  openDate,
  onOpen,
}: {
  list: NoteSummary[]
  days: DailyDay[]
  today: string
  /** The past date on screen, or null when today is. */
  openDate: string | null
  onOpen: (date: string | null) => void
}) {
  const past = list.map((n) => ({ date: dateOfDailyPath(n.path), path: n.path })).filter((d) => d.date !== today)
  const detail = new Map(days.map((d) => [d.date, d]))
  return (
    <Card>
      <CardHead title="Past standups" count={past.length} />
      <CardRow className="grid-cols-[minmax(0,1fr)_auto] p-0">
        <RowButton current={openDate === null} onClick={() => onOpen(null)} date={today} summary="Today" />
      </CardRow>
      {past.length === 0 ? (
        <EmptyState>No earlier daily notes yet. They appear here once you have started a standup on another day.</EmptyState>
      ) : (
        past.map((d) => {
          const day = detail.get(d.date)
          const summary = day ? `${day.sections.Done.length} done, ${day.sections.Today.length} planned` : 'N/A'
          return (
            <CardRow key={d.path} className="grid-cols-[minmax(0,1fr)_auto] p-0">
              <RowButton current={openDate === d.date} onClick={() => onOpen(d.date)} date={d.date} summary={summary} />
            </CardRow>
          )
        })
      )}
    </Card>
  )
}

function RowButton({ current, onClick, date, summary }: { current: boolean; onClick: () => void; date: string; summary: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={current ? 'true' : undefined}
      aria-label={`${formatDayTitle(date)}, ${summary}`}
      className={cn(
        'col-span-2 flex min-h-9 w-full cursor-pointer items-center justify-between gap-3 border-0 bg-transparent px-3 py-1 text-left text-ink hover:bg-inset max-rail:min-h-11',
        current && 'bg-inset font-semibold',
      )}
    >
      <span className="mono">{date}</span>
      <span className="t-caption text-muted-ink">{summary}</span>
    </button>
  )
}

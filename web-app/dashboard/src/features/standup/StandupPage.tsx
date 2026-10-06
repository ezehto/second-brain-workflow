import { useCallback, useMemo, useState } from 'react'
import { useApi } from '@/api/ApiProvider'
import { useQuery, type Query } from '@/api/useQuery'
import type { NoteDetail, StandupToday } from '@/api/types'
import { QueryBoundary } from '@/components/QueryBoundary'
import { Segmented } from '@/components/Segmented'
import { StatTile } from '@/components/StatTile'
import { dateOfDailyPath, openRuns, parseDaily, previewSections, previousDay, standupCounts, type DailyDay } from '@/domain/daily'
import { dailyPath } from '@/domain/standup'
import { useToday } from '@/lib/clock'
import { noteHref, routes, tasksHref } from '@/lib/routes'
import { DayPanel, type StandupView } from './DayPanel'
import { HistoryList } from './HistoryList'
import { Patterns } from './Patterns'
import { useHistory, useResolver } from './useStandupData'

type SideView = 'history' | 'patterns'

const GRID = 'grid grid-cols-[repeat(auto-fit,minmax(min(160px,100%),1fr))] gap-4'

function todayView(standup: StandupToday, today: string): StandupView {
  if (!standup.exists) {
    return { date: today, path: dailyPath(today), sections: previewSections(standup.preview), note: null, state: 'missing' }
  }
  return {
    date: today,
    path: standup.note.path,
    sections: parseDaily(standup.note.body),
    note: standup.note,
    state: standup.untouched ? 'untouched' : 'touched',
  }
}

function pastView(note: NoteDetail): StandupView {
  return { date: dateOfDailyPath(note.path), path: note.path, sections: parseDaily(note.body), note, state: 'past' }
}

/**
 * The Standup page: the six sections of one daily note on the left (today's by
 * default, a past one read-only), the past standups and the patterns computed
 * from them on the right. Everything is read from the daily notes; the only
 * writes are Start or Fill and Add, both through the standup endpoints.
 */
export function StandupPage() {
  const client = useApi()
  const today = useToday()
  const [openDate, setOpenDate] = useState<string | null>(null)
  const [side, setSide] = useState<SideView>('history')

  const standup = useQuery(useCallback(() => client.getStandupToday(), [client]))
  const history = useHistory()
  const historyList = history.status === 'success' ? history.data.list : undefined
  const pastPath = openDate ? (historyList?.find((n) => dateOfDailyPath(n.path) === openDate)?.path ?? null) : null
  const past: Query<NoteDetail | null> = useQuery(useCallback(async () => (pastPath ? client.lookupNote({ path: pastPath }) : null), [client, pastPath]))

  const view: Query<StandupView | null> = useMemo(() => {
    if (openDate) {
      if (past.status === 'success') return { ...past, data: past.data ? pastView(past.data) : null }
      return past as Query<StandupView | null>
    }
    if (standup.status === 'success') return { ...standup, data: todayView(standup.data, today) }
    return standup as Query<StandupView | null>
  }, [openDate, past, standup, today])

  const days = useMemo(() => (history.status === 'success' ? history.data.days : []), [history])
  const shown = view.status === 'success' ? view.data : null
  const resolver = useResolver(shown?.note ?? undefined)

  // Standups before the one on screen, newest first, with the one on screen at the head.
  const runDays: DailyDay[] = useMemo(() => {
    if (!shown) return []
    const earlier = days.filter((d) => d.date < shown.date)
    return [{ date: shown.date, path: shown.path, sections: shown.sections }, ...earlier]
  }, [shown, days])
  const todayRuns = useMemo(() => openRuns(runDays, 'Today'), [runDays])
  const yesterday = shown ? previousDay(days, shown.date) : null
  const counts = shown ? standupCounts(shown.sections, todayRuns) : null

  return (
    <div className="flex flex-col gap-5">
      <div className={GRID}>
        <StatTile compact icon="tasks" tone="progress" value={counts?.planned ?? 'N/A'} label="Planned today" to={tasksHref({ today: true })} />
        <StatTile compact icon="timeline" tone="risk" value={counts?.carried ?? 'N/A'} label="Carried over" to={tasksHref({ today: true })} />
        <StatTile compact icon="blocked" tone="blocked" value={counts?.blockers ?? 'N/A'} label="Blockers" to={tasksHref({ status: 'blocked' })} />
        <StatTile
          compact
          icon="flag"
          tone="review"
          value={counts?.followUps ?? 'N/A'}
          label="Follow-ups"
          to={shown?.note ? noteHref(shown.path) : routes.standups}
        />
      </div>

      <div className="flex flex-wrap items-start gap-5">
        <div className="flex min-w-0 flex-[2_1_480px] flex-col gap-5">
          <QueryBoundary query={view} rows={6}>
            {(v) =>
              v ? (
                <DayPanel key={v.path} view={v} yesterday={yesterday} todayRuns={todayRuns} resolver={resolver} onBack={openDate ? () => setOpenDate(null) : undefined} />
              ) : null
            }
          </QueryBoundary>
        </div>

        <aside aria-label="History and patterns" className="flex min-w-0 flex-[1_1_320px] flex-col gap-5 lg:max-w-[420px]">
          <Segmented
            label="Standup history views"
            value={side}
            onChange={setSide}
            options={[
              { value: 'history', label: 'History' },
              { value: 'patterns', label: 'Patterns' },
            ]}
          />
          <QueryBoundary query={history} rows={4}>
            {(h) =>
              side === 'history' ? (
                <HistoryList list={h.list} days={h.days} today={today} openDate={openDate} onOpen={setOpenDate} />
              ) : (
                <Patterns days={h.days} today={today} resolver={resolver} />
              )
            }
          </QueryBoundary>
        </aside>
      </div>
    </div>
  )
}

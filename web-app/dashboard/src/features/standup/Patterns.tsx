import { Link } from 'react-router'
import { Card, CardFootnote, CardHead, CardRow } from '@/components/Card'
import { EmptyState } from '@/components/EmptyState'
import { StatusChip } from '@/components/StatusChip'
import {
  CARRY_OVER_DAYS,
  WORK_WINDOW,
  carryOverItems,
  openFollowUps,
  openRuns,
  recurringBlockers,
  workByProject,
  type DailyDay,
} from '@/domain/daily'
import { formatShortDate } from '@/lib/dates'
import { plural } from '@/lib/plural'
import { projectHref } from '@/lib/routes'
import { LineText } from './LineRow'
import type { LinkResolver } from './links'

const NO_PROJECT = 'No project'

/** Four questions answered from the daily notes themselves (Phase 1 data), newest standup first. */
export function Patterns({ days, today, resolver }: { days: DailyDay[]; today: string; resolver: LinkResolver }) {
  const carry = carryOverItems(days)
  const shortRuns = openRuns(days, 'Today').filter((r) => r.standups > 1 && r.standups < CARRY_OVER_DAYS).length
  const blockers = recurringBlockers(days)
  const work = workByProject(days, resolver.projectOf)
  const followUps = openFollowUps(days, today)
  const workDays = days.slice(0, WORK_WINDOW)
  const max = Math.max(1, ...work.map((w) => w.count))

  return (
    <>
      <Card>
        <CardHead title="What keeps rolling over?" count={carry.length} />
        {carry.length === 0 ? (
          <EmptyState>Nothing has been in Today for {CARRY_OVER_DAYS} days in a row.</EmptyState>
        ) : (
          carry.map((r) => (
            <CardRow key={r.key} lines={2} className="grid-cols-[minmax(0,1fr)_auto]">
              <div className="flex min-w-0 flex-col">
                <span className="t-body truncate">
                  <LineText line={r.line} resolver={resolver} />
                </span>
                <span className="t-small text-muted-ink">
                  Since {formatShortDate(r.since)}, on {plural(r.standups, 'standup')} in a row
                </span>
              </div>
              <StatusChip label={`${r.standups} days`} tone="risk" />
            </CardRow>
          ))
        )}
        <CardFootnote>
          In Today for {CARRY_OVER_DAYS} or more standups in a row.
          {shortRuns > 0 && ` ${plural(shortRuns, 'other item')} carried over for less.`}
        </CardFootnote>
      </Card>

      <Card>
        <CardHead title="Which blockers keep coming back?" count={blockers.length} />
        {blockers.length === 0 ? (
          <EmptyState>No blocker has been listed on more than one day.</EmptyState>
        ) : (
          blockers.map((b) => (
            <CardRow key={b.key} lines={2} className="grid-cols-[minmax(0,1fr)_auto]">
              <div className="flex min-w-0 flex-col">
                <span className="t-body truncate">{b.label}</span>
                <span className="t-small truncate text-muted-ink">
                  {b.dates.map(formatShortDate).join(', ')}
                  {b.blockedBy ? `. Blocked by: ${b.blockedBy}` : ''}
                </span>
              </div>
              <StatusChip label={`${b.dates.length} days`} tone="blocked" />
            </CardRow>
          ))
        )}
      </Card>

      <Card>
        <CardHead title="Where did the work go?" />
        {work.length === 0 ? (
          <EmptyState>Nothing has been listed under Done yet.</EmptyState>
        ) : (
          <ul className="m-0 list-none p-0">
            {work.map((w) => {
              const title = w.slug ? (resolver.projectTitle(w.slug) ?? `${w.slug} (unknown)`) : NO_PROJECT
              return (
                <CardRow key={w.slug ?? 'none'} className="grid-cols-[7rem_minmax(0,1fr)_1.5rem]" role="listitem">
                  <span className="t-small truncate">
                    {w.slug && resolver.projectTitle(w.slug) ? (
                      <Link to={projectHref(w.slug)} className="linkbtn">
                        {title}
                      </Link>
                    ) : (
                      <span className="text-muted-ink">{title}</span>
                    )}
                  </span>
                  <span aria-hidden="true" className="h-3 overflow-hidden rounded-full bg-inset">
                    <span className="block h-3 rounded-full bg-status-done" style={{ width: `${(w.count / max) * 100}%` }} />
                  </span>
                  <span className="num t-body text-right font-bold">{w.count}</span>
                </CardRow>
              )
            })}
          </ul>
        )}
        <CardFootnote>
          Lines under Done, last {plural(workDays.length, 'standup')}
          {workDays.length > 0 && ` (${formatShortDate(workDays[workDays.length - 1].date)} to ${formatShortDate(workDays[0].date)})`}.
        </CardFootnote>
      </Card>

      <Card>
        <CardHead title="Which follow-ups are still open?" count={followUps.length} />
        {followUps.length === 0 ? (
          <EmptyState>No unchecked follow-ups.</EmptyState>
        ) : (
          followUps.map((f) => (
            <CardRow key={f.key} lines={2} className="grid-cols-[minmax(0,1fr)_auto]">
              <div className="flex min-w-0 flex-col">
                <span className="t-body truncate">
                  <LineText line={f.line} resolver={resolver} />
                </span>
                <span className="t-small text-muted-ink">First listed {formatShortDate(f.since)}</span>
              </div>
              <span className="num t-small text-muted-ink">{f.ageDays === 0 ? 'Today' : plural(f.ageDays, 'day')}</span>
            </CardRow>
          ))
        )}
      </Card>
    </>
  )
}

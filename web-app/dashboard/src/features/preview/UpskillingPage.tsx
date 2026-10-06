import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { Card, CardFootnote, CardHead, CardRow } from '@/components/Card'
import { ProgressBar } from '@/components/ProgressBar'
import { StatTile } from '@/components/StatTile'
import { StatusChip } from '@/components/StatusChip'
import { useToast } from '@/components/Toast'
import { Button } from '@/components/ui/button'
import { formatShortDate } from '@/lib/dates'
import { noteHref, routes } from '@/lib/routes'
import { cn } from '@/lib/utils'
import { previewUpskilling } from '@/preview'
import { PreviewBanner } from './controls'
import {
  CHAIN_LABELS,
  LEVEL_TONE,
  WEEK_WORD,
  filledSteps,
  groupByCategory,
  monthDay,
  notePath,
  weekFile,
  weekStart,
  weekState,
  weeklyCounts,
} from './upskilling'

const { themes, currentWeek, roadmapStart, weekStates, skills, notes, recommendations, source } = previewUpskilling
const SERIES = [
  { key: 'applied', label: 'Applied', color: 'var(--color-status-done)' },
  { key: 'practice', label: 'Practice', color: 'var(--color-status-review)' },
  { key: 'learning', label: 'Learning', color: 'var(--color-status-progress)' },
] as const
const SKILLS_ANCHOR = `${routes.upskilling}#skills`
const WEEKLY_ANCHOR = `${routes.upskilling}#learning-per-week`

type RecState = 'suggested' | 'accepted' | 'dismissed'

/** Phase 3 preview: this week's roadmap, what real work says to learn next, and how the skills are progressing. */
export function UpskillingPage() {
  const toast = useToast()
  const [selectedSkill, setSelectedSkill] = useState('idempotency')
  const [checks, setChecks] = useState<Record<string, boolean>>(() => Object.fromEntries(previewUpskilling.checklist.map((c) => [c.id, c.done])))
  const [recState, setRecState] = useState<Record<string, RecState>>({})

  const counts = useMemo(() => weeklyCounts(notes, roadmapStart, currentWeek), [])
  const thisWeek = counts[currentWeek - 1]
  const doneCount = Object.values(checks).filter(Boolean).length
  const total = previewUpskilling.checklist.length
  const gaps = skills.filter((s) => s.gap).length
  const skill = skills.find((s) => s.id === selectedSkill) ?? skills[0]
  const week = weekFile(currentWeek)
  const start = weekStart(roadmapStart, currentWeek)

  const decide = (id: string, state: RecState, message: string) => {
    setRecState((s) => ({ ...s, [id]: state }))
    toast.show(message)
  }

  const byDate = (a: { date: string }, b: { date: string }) => (a.date < b.date ? 1 : -1)
  const learned = notes
    .filter((n) => n.kind === 'learning')
    .sort(byDate)
    .slice(0, 4)
  const practiced = notes
    .filter((n) => n.kind !== 'learning')
    .sort(byDate)
    .slice(0, 4)

  return (
    <div className="flex flex-col gap-4">
      <PreviewBanner phase="Phase 3" what="Upskilling needs the 06-Upskilling notes and the roadmap." source={source} />

      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(200px,100%),1fr))] gap-4">
        <StatTile compact icon="calendar" tone="progress" value={`${currentWeek} of ${themes.length}`} label="Roadmap week" to={noteHref(week)} />
        <StatTile compact icon="flag" tone="risk" value={gaps} label="Skill gaps from real work" to={SKILLS_ANCHOR} />
        <StatTile compact icon="book" tone="review" value={thisWeek.practice} label="Practice notes this week" to={WEEKLY_ANCHOR} />
        <StatTile compact icon="tasks" tone="done" value={thisWeek.applied} label="Applied to a project this week" to={WEEKLY_ANCHOR} />
      </div>

      <div className="flex flex-wrap items-start gap-4">
        <Card className="flex-[7_1_520px]">
          <CardHead title={`Week ${currentWeek}: ${themes[currentWeek - 1]}`} count={`${doneCount} of ${total} done`} />
          <p className="t-small m-0 px-3 pb-2 text-muted-ink">
            {monthDay(start)} to {monthDay(start + 6 * 86_400_000)}, 2026. Next week: {themes[currentWeek]}.
          </p>
          <div className="flex items-center gap-3 px-3 pb-2">
            <ProgressBar percent={Math.round((doneCount / total) * 100)} label="This week's checklist" />
            <span className="num t-small text-muted-ink">
              {doneCount}/{total}
            </span>
          </div>
          <ul className="m-0 list-none p-0">
            {previewUpskilling.checklist.map((c) => (
              <li key={c.id}>
                <CardRow lines={c.done && c.note ? 2 : 1} className="grid-cols-[auto_minmax(0,1fr)]">
                  <input
                    id={`chk-${c.id}`}
                    type="checkbox"
                    checked={checks[c.id]}
                    className="size-4 cursor-pointer accent-[var(--color-brand-fill)]"
                    onChange={() => {
                      setChecks((s) => ({ ...s, [c.id]: !s[c.id] }))
                      toast.show(`Would update the checklist in ${week}`)
                    }}
                  />
                  <span className="flex min-w-0 flex-col">
                    <label htmlFor={`chk-${c.id}`} className={cn('t-body cursor-pointer', checks[c.id] && 'text-muted-ink line-through')}>
                      {c.text}
                    </label>
                    {checks[c.id] && c.note && <span className="t-small text-muted-ink">Evidence: {c.note}</span>}
                  </span>
                </CardRow>
              </li>
            ))}
          </ul>
          <div className="border-t border-line px-3 py-2">
            <h3 className="t-small mb-1 font-semibold">The 17-week roadmap</h3>
            <ol className="m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(32px,1fr))] gap-1 p-0">
              {themes.map((theme, i) => {
                const n = i + 1
                const state = weekState(n, currentWeek, weekStates)
                return (
                  <li
                    key={theme}
                    title={`Week ${n}: ${theme}`}
                    aria-label={`Week ${n}, ${WEEK_WORD[state].toLowerCase()}, ${theme}`}
                    className={cn(
                      'flex h-10 flex-col items-center justify-center rounded-btn border',
                      state === 'current' ? 'border-brand' : 'border-line',
                    )}
                  >
                    <span aria-hidden="true" className="num t-small font-semibold">
                      {n}
                    </span>
                    <span
                      aria-hidden="true"
                      className={cn(
                        't-small font-bold',
                        state === 'done' && 'text-status-done',
                        state === 'partly' && 'text-status-risk',
                        state === 'current' && 'text-ink',
                        state === 'upcoming' && 'text-muted-ink',
                      )}
                    >
                      {{ done: '✓', partly: '◐', current: '●', upcoming: '·' }[state]}
                    </span>
                  </li>
                )
              })}
            </ol>
            <p className="t-caption m-0 mt-1 text-muted-ink">✓ done, ◐ partly done, ● this week, · not started. Hover a week for its theme.</p>
          </div>
        </Card>

        <Card className="flex-[5_1_380px]">
          <CardHead title="What to learn next" count={recommendations.length} />
          {recommendations.map((r) => {
            const state = recState[r.id] ?? 'suggested'
            const sk = skills.find((s) => s.id === r.skillId)!
            const file = `06-Upskilling/Skills/${sk.name}.md`
            return (
              <article key={r.id} aria-label={r.title} className="flex flex-col gap-1 border-t border-line px-3 py-2">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <h3 className="t-body font-semibold">{r.title}</h3>
                  <StatusChip
                    tone={state === 'accepted' ? 'done' : state === 'dismissed' ? 'cancelled' : 'review'}
                    label={
                      {
                        suggested: 'Suggested',
                        accepted: 'Accepted',
                        dismissed: 'Dismissed',
                      }[state]
                    }
                  />
                </div>
                <p className="t-small m-0 text-muted-ink">
                  {r.project} · skill{' '}
                  <button
                    type="button"
                    className="linkbtn t-small cursor-pointer border-0 bg-transparent p-0 text-brand underline-offset-2 hover:underline"
                    onClick={() => setSelectedSkill(sk.id)}
                  >
                    {sk.name}
                  </button>
                </p>
                <p className="t-small m-0">{r.why}</p>
                <p className="t-small m-0 text-muted-ink">{r.fit}</p>
                <p className="t-caption m-0 text-muted-ink">Evidence: {r.evidence.map((e) => `${e.kind}, ${e.title}`).join('; ')}</p>
                <div className="flex gap-2">
                  {state === 'suggested' ? (
                    <>
                      <Button type="button" size="sm" onClick={() => decide(r.id, 'accepted', `Would add a next action to ${file}`)}>
                        Accept
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        onClick={() => decide(r.id, 'dismissed', `Would record the dismissal in ${file} so it is not suggested again`)}
                      >
                        Dismiss
                      </Button>
                    </>
                  ) : (
                    <Button type="button" size="sm" variant="ghost" onClick={() => decide(r.id, 'suggested', 'Back to suggested, no file changed')}>
                      Undo
                    </Button>
                  )}
                </div>
              </article>
            )
          })}
        </Card>
      </div>

      <div id="skills" className="flex flex-wrap items-start gap-4">
        <Card className="flex-[5_1_380px]">
          <CardHead title="Skills" count={`${skills.length}, ${gaps} with a gap`} />
          <ul className="m-0 max-h-[336px] list-none overflow-y-auto p-0" aria-label="Skills">
            {skills.map((s) => {
              const on = s.id === skill.id
              return (
                <li key={s.id}>
                  <CardRow className={cn('p-0', on && 'bg-inset')}>
                    <button
                      type="button"
                      aria-pressed={on}
                      onClick={() => setSelectedSkill(s.id)}
                      className="grid w-full cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 border-0 bg-transparent px-3 py-1 text-left text-ink hover:bg-inset"
                    >
                      <span className="t-body truncate font-medium">{s.name}</span>
                      <span className="t-small text-muted-ink">
                        {s.gap && <span className="mr-2 font-semibold text-status-risk">Gap</span>}
                        {filledSteps(s)} of 7 steps
                      </span>
                    </button>
                  </CardRow>
                </li>
              )
            })}
          </ul>
        </Card>

        <Card className="flex-[7_1_520px]" aria-label="Gap to lesson chain">
          <CardHead title={`Problem to lesson: ${skill.name}`} count={`${filledSteps(skill)} of 7`} />
          <ol className="m-0 list-none p-0">
            {skill.chain.map((title, i) => (
              <li key={CHAIN_LABELS[i]}>
                <CardRow className="grid-cols-[24px_132px_minmax(0,1fr)]">
                  <span
                    aria-hidden="true"
                    className={cn(
                      'num t-small flex size-6 items-center justify-center rounded-full border',
                      title ? 'border-status-done text-status-done' : 'border-dashed border-line text-muted-ink',
                    )}
                  >
                    {i + 1}
                  </span>
                  <span className="t-small font-semibold">{CHAIN_LABELS[i]}</span>
                  {title ? (
                    <Link to={noteHref(`06-Upskilling/${title}.md`)} className="t-body truncate">
                      {title}
                    </Link>
                  ) : (
                    <span className="t-small text-muted-ink">No note yet</span>
                  )}
                </CardRow>
              </li>
            ))}
          </ol>
          <CardFootnote>
            {skill.chain.every(Boolean) ? 'Every step has a note.' : `Next: ${CHAIN_LABELS[skill.chain.findIndex((t) => !t)]} has no note yet.`}
            {skill.gap ? ` Gap: ${skill.gap}${skill.project ? ` (${skill.project})` : ''}.` : ' No gap recorded from real work.'}
          </CardFootnote>
        </Card>
      </div>

      <div id="learning-per-week" className="flex flex-wrap items-start gap-4">
        <Card className="flex-[5_1_380px]">
          <CardHead title="How much did you learn each week?" count={`${notes.length} notes`}>
            <ul className="m-0 flex list-none flex-wrap gap-x-3 p-0">
              {[...SERIES].reverse().map((s) => (
                <li key={s.key} className="t-small flex items-center gap-1.5">
                  <span aria-hidden="true" className="size-2 rounded-full" style={{ background: s.color }} />
                  {s.label}
                  <span className="num text-muted-ink">{counts.reduce((a, c) => a + c[s.key], 0)}</span>
                </li>
              ))}
            </ul>
          </CardHead>
          <ol className="m-0 flex list-none items-end gap-3 px-3 pb-2 p-0" aria-label="Notes per week">
            {counts.map((c) => (
              <li
                key={c.week}
                className="flex flex-1 flex-col items-center gap-1"
                aria-label={`Week ${c.week}: ${c.learning} learning, ${c.practice} practice, ${c.applied} applied`}
              >
                <span className="num t-small font-semibold">{c.total}</span>
                <span aria-hidden="true" className="flex w-full max-w-10 flex-col gap-0.5">
                  {SERIES.map((s) =>
                    c[s.key] > 0 ? (
                      <span
                        key={s.key}
                        className="num t-small flex items-center justify-center rounded-md font-semibold text-ground"
                        style={{
                          background: s.color,
                          height: c[s.key] * 20 + (c[s.key] - 1) * 2,
                        }}
                      >
                        {c[s.key]}
                      </span>
                    ) : null,
                  )}
                </span>
                <span aria-hidden="true" className="t-caption text-muted-ink">
                  W{c.week}
                </span>
              </li>
            ))}
          </ol>
        </Card>

        <Card className="flex-[7_1_520px]">
          <CardHead title="Where are you strong, by area?" count={`${groupByCategory(skills).length} areas`} />
          {groupByCategory(skills).map(([category, list]) => (
            <CardRow key={category} className="grid-cols-[120px_minmax(0,1fr)]">
              <span className="t-body font-semibold">{category}</span>
              <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-0 p-0">
                {list.map((s) => (
                  <li key={s.id} className="t-small flex items-center gap-1.5">
                    {s.name}
                    <StatusChip tone={LEVEL_TONE[s.level]} label={s.level} />
                  </li>
                ))}
              </ul>
            </CardRow>
          ))}
          <CardFootnote>Levels are words, not scores: Aware, Practicing, Applied, Can teach. A level moves when a note proves it.</CardFootnote>
        </Card>
      </div>

      <div className="grid min-w-0  grid-cols-[repeat(auto-fit,minmax(min(260px,100%),1fr))] gap-4">
        <RecentList title="Recently learned" list={learned} />
        <RecentList title="Recently practiced and applied" list={practiced} />
      </div>
    </div>
  )
}

function RecentList({ title, list }: { title: string; list: typeof notes }) {
  return (
    <Card>
      <CardHead title={title} count={list.length} />
      {list.map((n) => (
        <CardRow key={n.title} lines={2} className="grid-cols-[minmax(0,1fr)_auto]">
          <span className="flex min-w-0 flex-col">
            <Link to={noteHref(notePath(n))} className="t-body truncate font-medium">
              {n.title}
            </Link>
            <span className="t-small truncate text-muted-ink">
              {n.skill}
              {n.kind === 'applied' ? ` · applied${n.project ? ` in ${n.project}` : ''}` : ''}
            </span>
          </span>
          <span className="num t-caption text-muted-ink">{formatShortDate(n.date)}</span>
        </CardRow>
      ))}
    </Card>
  )
}

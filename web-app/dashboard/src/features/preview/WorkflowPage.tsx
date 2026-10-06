import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'
import { Card, CardFootnote, CardHead, CardRow } from '@/components/Card'
import { Segmented } from '@/components/Segmented'
import { StatusChip } from '@/components/StatusChip'
import { useToast } from '@/components/Toast'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { TONE_TEXT } from '@/domain/status'
import { formatShortDate } from '@/lib/dates'
import { cn } from '@/lib/utils'
import { PREVIEW_PROJECTS, previewWorkflowItems, type LoopEntry, type PreviewWorkflowItem } from '@/preview'
import { LabelledSelect, PreviewBanner } from './controls'
import {
  CAUSE_ORDER,
  CAUSES,
  STAGE_HINT,
  STAGE_SHORT,
  allowedModes,
  applyAction,
  derive,
  statusOf,
  statusTone,
  validate,
  type ActionInput,
  type ActionMode,
} from './workflow'

const { stageNames, asOf, source } = previewWorkflowItems
const PROJECT_OPTIONS = [{ value: 'all', label: 'All' }, ...['loadup', 'ipp', 'second-brain'].map((p) => ({ value: p, label: PREVIEW_PROJECTS[p] }))]
const EMPTY_INPUT: ActionInput = { mode: 'test', result: 'pass', cause: '', note: '' }
const MODE_TITLE: Record<ActionMode, string> = { test: 'Record test result', review: 'Record review result', back: 'Send back' }

/** Phase 2 preview: where each item sits in the closed loop, and what a failure sends it back to. */
export function WorkflowPage() {
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const project = params.get('project') ?? 'all'
  const [items, setItems] = useState<PreviewWorkflowItem[]>(previewWorkflowItems.items)
  const [selectedId, setSelectedId] = useState('retry')
  const [input, setInput] = useState<ActionInput | null>(null)

  const shown = useMemo(() => items.filter((i) => project === 'all' || i.project === project), [items, project])
  const derived = useMemo(() => new Map(shown.map((i) => [i.id, derive(i, stageNames)])), [shown])
  const selected = shown.find((i) => i.id === selectedId) ?? shown[0]

  const setProject = (value: string) => {
    const next = new URLSearchParams(params)
    if (value === 'all') next.delete('project')
    else next.set('project', value)
    setParams(next, { replace: true })
    setInput(null)
  }
  const select = (id: string) => {
    setSelectedId(id)
    setInput(null)
  }

  const submit = () => {
    if (!selected || !input) return
    const { item, message } = applyAction(selected, input, asOf, stageNames)
    setItems((all) => all.map((i) => (i.id === item.id ? item : i)))
    setInput(null)
    toast.show(message)
  }

  const backward = useMemo(() => {
    const moves = new Map<string, number>()
    shown.forEach((i) =>
      i.history.forEach((e, k) => {
        const next = i.history[k + 1]
        if (e.kind === 'fail' && next)
          moves.set(
            `${stageNames[e.stage]} to ${stageNames[next.stage]}`,
            (moves.get(`${stageNames[e.stage]} to ${stageNames[next.stage]}`) ?? 0) + 1,
          )
      }),
    )
    return [...moves].sort((a, b) => b[1] - a[1])
  }, [shown])

  return (
    <div className="flex flex-col gap-4">
      <PreviewBanner phase="Phase 2" what="The closed-loop workflow needs a stage and a loop history on each task." source={source} />

      <Card>
        <CardHead title="Where work sits" count={`${shown.length} items`}>
          <Segmented label="Project" options={PROJECT_OPTIONS} value={project} onChange={setProject} />
        </CardHead>
        <ol className="m-0 grid list-none grid-cols-2 border-t border-line p-0 sm:grid-cols-3 xl:grid-cols-6" aria-label="Workflow stages">
          {stageNames.map((name, i) => {
            const inStage = shown.filter((x) => x.stage === i)
            const back = inStage.filter((x) => derived.get(x.id)?.sentBack).length
            const blocked = inStage.filter((x) => x.blocked).length
            return (
              <li key={name} className="flex flex-col gap-0.5 border-r border-b border-line px-3 py-2 last:border-r-0 xl:border-b-0">
                <span className="flex items-baseline gap-2">
                  <span className="num t-page font-bold">{inStage.length}</span>
                  <span className="t-body font-semibold">{name}</span>
                </span>
                <span className="t-caption flex flex-wrap gap-x-3 text-muted-ink">
                  <span className={cn(back > 0 && 'font-semibold text-status-blocked')}>{back} sent back</span>
                  <span className={cn(blocked > 0 && 'font-semibold text-status-blocked')}>{blocked} blocked</span>
                </span>
              </li>
            )
          })}
        </ol>
        <p className="t-small m-0 border-t border-line px-3 py-2">
          <span className="font-semibold">Backward moves: </span>
          {backward.length === 0 ? (
            <span className="text-muted-ink">none. Nothing has been sent back.</span>
          ) : (
            backward.map(([text, n], i) => (
              <span key={text} className="text-muted-ink">
                {i > 0 && ', '}
                {text} <span className="num font-semibold text-ink">{n}</span>
              </span>
            ))
          )}
        </p>
      </Card>

      <div className="flex flex-wrap items-start gap-4">
        <Card className="flex-[7_1_520px]">
          <CardHead title="Items by stage" count={shown.length} />
          {shown.length === 0 && <p className="m-0 px-3 pb-3 text-muted-ink">No items in this project. Pick All to see every item.</p>}
          {stageNames.map((name, i) => {
            const rows = shown.filter((x) => x.stage === i)
            if (rows.length === 0) return null
            return (
              <div key={name} role="group" aria-label={name}>
                <div className="flex min-h-9 flex-wrap items-baseline gap-x-2 border-t border-line bg-inset px-3 py-1">
                  <h3 className="t-body font-semibold">{name}</h3>
                  <span className="num t-numeral text-muted-ink">{rows.length}</span>
                  <span className="t-caption text-muted-ink">{STAGE_HINT[i]}</span>
                </div>
                {rows.map((item) => (
                  <ItemRow key={item.id} item={item} d={derived.get(item.id)!} selected={item.id === selected?.id} onSelect={() => select(item.id)} />
                ))}
              </div>
            )
          })}
        </Card>

        <div className="flex min-w-0 flex-[5_1_380px] flex-col gap-4">
          {selected ? (
            <LoopPanel item={selected} input={input} setInput={setInput} onSubmit={submit} />
          ) : (
            <Card>
              <CardHead title="Loop history" />
              <p className="m-0 px-3 pb-3 text-muted-ink">Select an item to see its loop history.</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

function ItemRow({
  item,
  d,
  selected,
  onSelect,
}: {
  item: PreviewWorkflowItem
  d: ReturnType<typeof derive>
  selected: boolean
  onSelect: () => void
}) {
  const done = item.stage === 5
  const detail = item.blocked ? `Blocked: ${item.blocker}` : d.sentBack ? `Sent back, ${d.failWord}. ${d.failNote}` : item.action
  return (
    <CardRow lines={done ? 1 : 2} className={cn('p-0', selected && 'bg-inset')}>
      <button
        type="button"
        aria-pressed={selected}
        onClick={onSelect}
        className="grid w-full cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 border-0 bg-transparent px-3 py-1 text-left text-ink hover:bg-inset"
      >
        <span className="flex min-w-0 flex-col">
          <span className="flex min-w-0 items-center gap-2">
            <span className="t-body truncate font-medium">{item.title}</span>
            {d.sentBack && <span className="t-caption flex-none font-semibold text-status-blocked">Sent back</span>}
            {item.blocked && <StatusChip status="blocked" />}
          </span>
          {!done && <span className={cn('t-small truncate', d.sentBack || item.blocked ? TONE_TEXT.blocked : 'text-muted-ink')}>{detail}</span>}
        </span>
        <span className="t-small flex flex-none flex-col items-end text-muted-ink max-sm:hidden">
          <span>
            {PREVIEW_PROJECTS[item.project]} · {item.owner}
          </span>
          <span className={cn(d.rework >= 2 && 'font-semibold text-status-blocked')}>Rework {d.rework}</span>
        </span>
      </button>
    </CardRow>
  )
}

function trailLabel(e: LoopEntry, afterFail: boolean): { text: string; cls: string } {
  if (e.kind === 'fail') return { text: `${e.source}, ${CAUSES[e.cause].label.toLowerCase()}`, cls: 'text-status-blocked' }
  if (e.kind === 'pass') return { text: e.stage === 3 ? 'Tests passed' : 'Review passed', cls: 'text-status-done' }
  return afterFail ? { text: `Back to ${stageNames[e.stage].toLowerCase()}`, cls: 'text-status-blocked' } : { text: stageNames[e.stage], cls: '' }
}

function LoopPanel({
  item,
  input,
  setInput,
  onSubmit,
}: {
  item: PreviewWorkflowItem
  input: ActionInput | null
  setInput: (i: ActionInput | null) => void
  onSubmit: () => void
}) {
  const d = derive(item, stageNames)
  const allowed = allowedModes(item)
  const problem = input ? validate(item, input) : null
  const showCause = input && (input.mode === 'back' || input.result === 'fail')
  const sameLabel = d.sameCause ? CAUSES[d.sameCause].label.toLowerCase() : ''
  const open = (mode: ActionMode) => setInput({ ...EMPTY_INPUT, mode })

  return (
    <Card aria-label="Loop history of the selected item">
      <CardHead title="Loop history">
        <StatusChip status={statusOf(item)} tone={statusTone(item)} label={`${stageNames[item.stage]}${item.blocked ? ', blocked' : ''}`} />
      </CardHead>
      <div className="border-t border-line px-3 py-2">
        <p className="t-body m-0 font-semibold">{item.title}</p>
        <p className="t-small m-0 text-muted-ink">
          {PREVIEW_PROJECTS[item.project]} · owner {item.owner} · previous {d.previous} · next {d.next} · rework {d.rework}
        </p>
        <p className="t-small m-0 mt-1">
          <span className="font-semibold">Required action: </span>
          {item.action}
        </p>
        {item.blocked && (
          <p className="t-small m-0 text-status-blocked">
            <span className="font-semibold">Blocker: </span>
            {item.blocker}
          </p>
        )}
      </div>

      <div className="border-t border-line" role="list" aria-label="Loop history entries">
        <div aria-hidden="true" className="t-caption grid grid-cols-[48px_repeat(6,16px)_minmax(0,1fr)] gap-x-1 px-3 pt-2 text-muted-ink">
          <span />
          {STAGE_SHORT.map((s) => (
            <span key={s} title={s} className="text-center">
              {s[0]}
            </span>
          ))}
          <span className="pl-2">Step</span>
        </div>
        {item.history.map((e, i) => {
          const afterFail = i > 0 && item.history[i - 1].kind === 'fail'
          const label = trailLabel(e, afterFail)
          const note = 'note' in e ? e.note : ''
          return (
            <div key={i} role="listitem" className="grid min-h-9 grid-cols-[48px_repeat(6,16px)_minmax(0,1fr)] items-center gap-x-1 px-3 py-1">
              <span className="num t-caption text-muted-ink">{formatShortDate(e.date)}</span>
              {STAGE_SHORT.map((_, c) => {
                const on = c === e.stage
                return (
                  <span key={c} aria-hidden="true" className="flex h-4 items-center justify-center">
                    {on &&
                      (e.kind === 'stage' && !afterFail ? (
                        <span className="size-2 rounded-full bg-ink" />
                      ) : (
                        <span className={cn('t-small font-bold', e.kind === 'pass' ? 'text-status-done' : 'text-status-blocked')}>
                          {e.kind === 'fail' ? '×' : e.kind === 'pass' ? '✓' : '←'}
                        </span>
                      ))}
                  </span>
                )
              })}
              <span className="flex min-w-0 flex-col pl-2">
                <span className={cn('t-small font-medium', label.cls)}>
                  {label.text}
                  {i === item.history.length - 1 && <span className="t-caption ml-2 font-normal text-muted-ink">Now</span>}
                </span>
                {note && <span className="t-caption text-muted-ink">{note}</span>}
              </span>
            </div>
          )
        })}
      </div>

      {(d.warned || d.stopped) && (
        <div className={cn('t-small mx-3 mb-3 rounded-btn px-3 py-2', d.stopped ? 'bg-tint-blocked' : 'bg-tint-risk')}>
          <p className={cn('m-0 font-semibold', d.stopped ? 'text-status-blocked' : 'text-status-risk')}>
            {d.stopped ? 'Stop rule reached' : 'Warning: two failures of the same kind'}
          </p>
          <p className="m-0">
            {d.stopped
              ? `Three failures of the same kind (${sameLabel}). Stop patching, analyse the root cause, review assumptions, requirements and architecture, then replan.`
              : `Two failures of the same kind (${sameLabel}). Three failures of the same kind stop the loop and trigger a replan.`}
          </p>
        </div>
      )}
      {d.sentBack && d.lastFail && (
        <p className="t-small m-0 border-t border-line px-3 py-2">
          <span className="font-semibold">{CAUSES[d.lastFail.cause].code}: </span>
          <span className="text-muted-ink">{CAUSES[d.lastFail.cause].rule}</span>
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2 border-t border-line px-3 py-2">
        {(['test', 'review', 'back'] as const).map((m) => (
          <Button
            key={m}
            type="button"
            size="sm"
            variant={input?.mode === m ? 'default' : 'secondary'}
            disabled={!allowed[m]}
            onClick={() => open(m)}
          >
            {MODE_TITLE[m]}
          </Button>
        ))}
        {!allowed.test && !allowed.review && !allowed.back && <span className="t-small text-muted-ink">Complete. Nothing left to record.</span>}
      </div>

      {input && (
        <form
          aria-label={MODE_TITLE[input.mode]}
          className="flex flex-col gap-2 border-t border-line px-3 py-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (!problem) onSubmit()
          }}
        >
          {input.mode !== 'back' && (
            <Segmented
              label="Result"
              options={[
                { value: 'pass', label: 'Passed' },
                { value: 'fail', label: 'Failed' },
              ]}
              value={input.result}
              onChange={(result) => setInput({ ...input, result, cause: '' })}
            />
          )}
          {showCause && (
            <>
              <LabelledSelect
                id="wf-cause"
                label="Cause"
                value={input.cause}
                onChange={(e) => setInput({ ...input, cause: e.target.value as ActionInput['cause'] })}
              >
                <option value="">Pick a cause</option>
                {CAUSE_ORDER.map((c) => (
                  <option key={c} value={c}>
                    {CAUSES[c].label}
                  </option>
                ))}
              </LabelledSelect>
              <p className="t-small m-0 text-muted-ink">
                {problem ??
                  `Moves to ${stageNames[CAUSES[input.cause as keyof typeof CAUSES].dest]}. ${CAUSES[input.cause as keyof typeof CAUSES].rule}`}
              </p>
            </>
          )}
          <label htmlFor="wf-note" className="t-small text-muted-ink">
            Note
          </label>
          <Textarea id="wf-note" rows={2} value={input.note} onChange={(e) => setInput({ ...input, note: e.target.value })} />
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={!!problem}>
              {input.mode === 'back' ? 'Send back' : 'Record result'}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setInput(null)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
      <CardFootnote>Writes {`02-Work/Tasks/${item.title}.md`}: stage, status, rework and failure fields.</CardFootnote>
    </Card>
  )
}

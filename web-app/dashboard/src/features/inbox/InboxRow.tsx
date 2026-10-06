import { useId, useRef, useState, type KeyboardEvent } from 'react'
import { useApi, useInvalidate } from '@/api/ApiProvider'
import { ApiError } from '@/api/client'
import type { NoteDetail, TriageAction } from '@/api/types'
import { CardRow } from '@/components/Card'
import { useToast } from '@/components/Toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { CLASSIFICATIONS, actionLabel, captureText, capturedWhen, conversionOf, writtenClassification } from './classify'
import type { Handled } from './HandledList'

const SELECT_CLASS =
  'h-8 min-w-0 rounded-btn border border-line bg-inset px-2 t-body text-ink focus-visible:border-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand max-rail:min-h-11'

/**
 * One capture awaiting triage, a 48px row: the text, when it was captured,
 * and the actions. With no written classification the row offers a labelled
 * select; the single action button's label follows the chosen kind. A kind with
 * no Phase 1 target is written and kept (the row then offers only Dismiss).
 *
 * Every write sends the hash of the capture as shown. An error carrying
 * `created_target` (whatever its status) means the target note exists but the capture could not be
 * edited: the row says so and offers Retry, which re-reads the capture and
 * resends with `existing_target` so nothing is created twice. Any other 409 is
 * a stale view: reload and say so.
 */
export function InboxRow({
  note,
  today,
  active,
  selected,
  onSelect,
  onHandled,
}: {
  note: NoteDetail
  today: string
  /** The row that holds the roving tab stop. */
  active: boolean
  selected: boolean
  onSelect: (note: NoteDetail) => void
  onHandled: (item: Handled) => void
}) {
  const client = useApi()
  const invalidate = useInvalidate()
  const toast = useToast()
  const ids = useId()
  const rowRef = useRef<HTMLLIElement>(null)
  const text = captureText(note)
  const written = writtenClassification(note)
  const [chosen, setChosen] = useState('')
  const [title, setTitle] = useState('')
  const [busy, setBusy] = useState(false)
  const [partial, setPartial] = useState<{ target: string; action: TriageAction; classification: string } | null>(null)

  const classification = written || chosen
  // A written kind with no target (including one just kept: the refetch carries it) is only listed (plan 2.13).
  const kept = written !== '' && conversionOf(written) === null
  const converts = !kept && conversionOf(classification) !== null

  async function send(action: TriageAction, kind: string | undefined, existingTarget?: string) {
    setBusy(true)
    try {
      // After a partial failure the capture changed under us, so the retry reads it again.
      let hash = note.content_hash
      if (existingTarget) {
        const fresh = await client.lookupNote({ path: note.path })
        if (fresh.status !== 'inbox') {
          toast.show(`${text} changed in Obsidian, reloaded.`)
          setPartial(null)
          invalidate()
          return
        }
        hash = fresh.content_hash
      }
      const response = await client.triageCapture({
        path: note.path,
        expected_hash: hash,
        action,
        classification: kind || undefined,
        title: action !== 'keep' && action !== 'dismiss' && title.trim() ? title.trim() : undefined,
        existing_target: existingTarget,
      })
      setPartial(null)
      if (action === 'dismiss') {
        onHandled({ path: note.path, text, outcome: 'dismissed', written: note.path })
        toast.show(`Set status: dismissed in ${note.path}`)
      } else if (action === 'keep') {
        toast.show(`Wrote classification: ${kind} in ${note.path}. It stays in the inbox.`)
      } else {
        const file = response.target?.path ?? note.path
        onHandled({ path: note.path, text, outcome: 'converted', written: file })
        toast.show(`Created ${file}, capture marked triaged in ${note.path}`)
      }
      invalidate()
    } catch (error) {
      if (error instanceof ApiError && error.body?.created_target) {
        setPartial({ target: error.body.created_target, action, classification: kind ?? '' })
      } else if (error instanceof ApiError && (error.status === 409 || error.status === 404)) {
        toast.show(`${text} changed in Obsidian, reloaded.`)
        invalidate()
      } else {
        toast.show(error instanceof Error ? error.message : 'The capture could not be triaged.')
      }
    } finally {
      setBusy(false)
    }
  }

  function convert() {
    const conversion = conversionOf(classification)
    void send(conversion ?? 'keep', classification)
  }

  function onKeyDown(event: KeyboardEvent<HTMLLIElement>) {
    const row = rowRef.current
    if (!row) return
    const inside = event.target !== event.currentTarget
    if (event.key === 'Escape' && inside) {
      row.focus()
      return
    }
    if (inside) return
    if (event.key === 'Enter') {
      event.preventDefault()
      row.querySelector<HTMLElement>('[data-actions] select, [data-actions] button')?.focus()
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const rows = Array.from(row.parentElement?.querySelectorAll<HTMLElement>('[data-inbox-row]') ?? [])
      rows[rows.indexOf(row) + (event.key === 'ArrowDown' ? 1 : -1)]?.focus()
    }
  }

  return (
    <li
      ref={rowRef}
      data-inbox-row
      tabIndex={active ? 0 : -1}
      aria-label={text}
      onKeyDown={onKeyDown}
      className="list-none focus-visible:bg-inset focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand"
    >
      <CardRow lines={2} className={cn('flex flex-wrap', selected && 'bg-inset')}>
        <div className="flex min-w-0 flex-[1_1_240px] flex-col">
          <button type="button" onClick={() => onSelect(note)} aria-pressed={selected} aria-label={`Open ${text}`} className="t-body min-h-6 cursor-pointer truncate border-0 bg-transparent p-0 text-left text-ink hover:underline">
            {text}
          </button>
          <span className="t-small truncate text-muted-ink">
            Captured {capturedWhen(note, today)}
            {written ? ', classified by /triage' : ''}
          </span>
        </div>

        <div data-actions className="flex flex-wrap items-center gap-2">
          {classification && (written || kept) && (
            <span className="t-small inline-flex h-6 items-center rounded-full bg-inset px-2 font-semibold text-muted-ink">{classification}</span>
          )}
          {!written && !kept && (
            <>
              <label htmlFor={`${ids}-class`} className="sr-only">
                Classification of {text}
              </label>
              <select id={`${ids}-class`} className={SELECT_CLASS} value={chosen} disabled={busy} onChange={(e) => setChosen(e.target.value)}>
                <option value="">Choose classification</option>
                {CLASSIFICATIONS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </>
          )}
          {kept ? (
            <span className="t-small text-muted-ink">Kept in inbox until its phase exists</span>
          ) : (
            <>
              {converts && (
                <>
                  <label htmlFor={`${ids}-title`} className="sr-only">
                    Title of the new note (optional)
                  </label>
                  <Input id={`${ids}-title`} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title (optional)" className="w-44" autoComplete="off" disabled={busy} />
                </>
              )}
              <Button size="sm" disabled={busy || !classification || partial !== null} onClick={convert}>
                {classification ? actionLabel(classification) : 'Choose a classification'}
              </Button>
            </>
          )}
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => void send('dismiss', written || undefined)}>
            Dismiss
          </Button>
        </div>

        {partial && (
          <div role="alert" className="t-small flex w-full flex-wrap items-center gap-2 text-status-blocked">
            <span>
              Created {partial.target}, but the capture could not be updated.
            </span>
            <Button size="sm" variant="secondary" disabled={busy} onClick={() => void send(partial.action, partial.classification, partial.target)}>
              Retry
            </Button>
          </div>
        )}
      </CardRow>
    </li>
  )
}

import { useRef, useState } from 'react'
import { useApi, useInvalidate } from '@/api/ApiProvider'
import { ApiError } from '@/api/client'
import { STATUS_VOCABULARY, type NoteDetail, type NoteSummary } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Icon } from './Icon'
import { StatusChip } from './StatusChip'
import { useToast } from './Toast'

/**
 * Changes a note's status in place. The trigger is the status chip; the menu
 * lists the vocabulary for the note's type (plan section 2.3).
 *
 * - The new status shows at once (optimistic) and is dropped if the write fails.
 *   It also yields as soon as the note's own status changes, so a later change
 *   made in Obsidian is never hidden behind it.
 * - A 409 means the note changed in Obsidian, and a 404 that it was moved or
 *   deleted: everything refetches and the person is told. Any other error shows
 *   its message.
 * - Moving a task to done asks for optional evidence first, which the API
 *   appends under `## Notes`. The typed text survives a failed write.
 *
 * Pass `contentHash` from a `NoteDetail` you are showing, so a stale view is
 * caught as a 409. Without it (list pages) the note is read just before the
 * change: a status that differs from the one shown is treated as a 409 and
 * nothing is written. After a write the returned hash is used until the prop
 * catches up, so a second quick change does not conflict with the first.
 */
export function StatusMenu({
  note,
  contentHash,
  onChanged,
}: {
  note: Pick<NoteSummary, 'path' | 'type' | 'title' | 'status'>
  contentHash?: string
  onChanged?: (note: NoteDetail) => void
}) {
  const client = useApi()
  const invalidate = useInvalidate()
  const toast = useToast()
  const [optimistic, setOptimistic] = useState<{ from: string | null; status: string } | null>(null)
  const [written, setWritten] = useState<{ prop: string | undefined; hash: string } | null>(null)
  const [askEvidence, setAskEvidence] = useState(false)
  const [evidence, setEvidence] = useState('')
  const [busy, setBusy] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)

  // The vault's status wins as soon as it moves; the optimistic value only bridges the refetch.
  // Reset during render (not in an effect) so a revert to the original status is never masked.
  const [seenStatus, setSeenStatus] = useState(note.status)
  if (seenStatus !== note.status) {
    setSeenStatus(note.status)
    setOptimistic(null)
  }

  const shown = optimistic && optimistic.from === note.status ? optimistic.status : note.status
  const vocabulary = (STATUS_VOCABULARY as Record<string, readonly string[]>)[note.type]
  if (!vocabulary) return <StatusChip status={note.status} />

  function reloaded(message: string) {
    toast.show(message)
    invalidate()
  }

  async function change(status: string, withEvidence?: string) {
    setBusy(true)
    const before = shown
    setOptimistic({ from: note.status, status })
    try {
      let expected_hash: string
      if (contentHash !== undefined) {
        expected_hash = written && written.prop === contentHash ? written.hash : contentHash
      } else {
        const fresh = await client.lookupNote({ path: note.path })
        if (fresh.status !== before) {
          setOptimistic(null)
          reloaded(`${note.title} changed in Obsidian, reloaded.`)
          return
        }
        expected_hash = fresh.content_hash
      }
      const updated = await client.changeStatus({ path: note.path, status, expected_hash, evidence: withEvidence || undefined })
      if (contentHash !== undefined) setWritten({ prop: contentHash, hash: updated.content_hash })
      setEvidence('')
      onChanged?.(updated)
      toast.show(`Set status: ${status} in ${note.path}`)
      invalidate()
    } catch (error) {
      setOptimistic(null)
      if (error instanceof ApiError && error.status === 409) {
        reloaded(`${note.title} changed in Obsidian, reloaded.`)
      } else if (error instanceof ApiError && error.status === 404) {
        reloaded('Note moved or deleted in Obsidian, reloaded.')
      } else {
        toast.show(error instanceof Error ? error.message : 'The status could not be changed.')
      }
    } finally {
      setBusy(false)
    }
  }

  function choose(status: string) {
    if (busy || status === shown) return
    if (note.type === 'task' && status === 'done') {
      setAskEvidence(true)
      return
    }
    void change(status)
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            ref={triggerRef}
            type="button"
            aria-disabled={busy}
            aria-label={`Status: ${shown ?? 'N/A'}. Change status of ${note.title}`}
            className="-my-1 inline-flex h-8 cursor-pointer items-center gap-1 rounded-btn px-1 hover:bg-inset aria-disabled:opacity-60 max-rail:my-0 max-rail:min-h-11"
          >
            <StatusChip status={shown} />
            <Icon name="chevron" className="size-3.5 text-muted-ink" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44">
          <DropdownMenuRadioGroup value={shown ?? ''} onValueChange={choose}>
            {vocabulary.map((status) => (
              <DropdownMenuRadioItem key={status} value={status}>
                {status}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={askEvidence} onOpenChange={setAskEvidence}>
        <DialogContent
          showCloseButton={false}
          onCloseAutoFocus={(event) => {
            event.preventDefault()
            triggerRef.current?.focus()
          }}
        >
          <form
            className="flex flex-col gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              setAskEvidence(false)
              void change('done', evidence.trim())
            }}
          >
            <DialogHeader>
              <DialogTitle className="text-panel font-semibold">Mark as done</DialogTitle>
              <DialogDescription className="text-small text-muted-ink">{note.title}</DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-1">
              <Label htmlFor="status-evidence" className="text-caption font-semibold text-muted-ink">
                Evidence (optional, added under Notes)
              </Label>
              <Textarea id="status-evidence" rows={3} value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder="What shows it is done" autoFocus />
            </div>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setAskEvidence(false)}>
                Cancel
              </Button>
              <Button type="submit">Mark done</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}

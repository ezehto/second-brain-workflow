import { useState } from 'react'
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
 * - A 409 means the note changed in Obsidian: everything refetches and the
 *   person is told it was reloaded. Any other error shows its message.
 * - Moving a task to done asks for optional evidence first, which the API
 *   appends under `## Notes`.
 *
 * Pass `contentHash` from a `NoteDetail` you are showing, so a stale view is
 * caught as a 409. Without it the hash is read just before the change, which
 * still protects the write but not the person's view.
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
  const [askEvidence, setAskEvidence] = useState(false)
  const [evidence, setEvidence] = useState('')
  const [busy, setBusy] = useState(false)

  // The optimistic status only counts while the note still has the status it was set from;
  // once the refetched note arrives with a different status, the real one wins.
  const shown = optimistic && optimistic.from === note.status ? optimistic.status : note.status
  const vocabulary = (STATUS_VOCABULARY as Record<string, readonly string[]>)[note.type]
  if (!vocabulary) return <StatusChip status={note.status} />

  async function change(status: string, withEvidence?: string) {
    setBusy(true)
    setOptimistic({ from: note.status, status })
    try {
      const expected_hash = contentHash ?? (await client.lookupNote({ path: note.path })).content_hash
      const updated = await client.changeStatus({ path: note.path, status, expected_hash, evidence: withEvidence || undefined })
      onChanged?.(updated)
      toast.show(`Set status: ${status} in ${note.path}`)
      invalidate()
    } catch (error) {
      setOptimistic(null)
      if (error instanceof ApiError && error.status === 409) {
        toast.show(`${note.title} changed in Obsidian, reloaded.`)
        invalidate()
      } else {
        toast.show(error instanceof Error ? error.message : 'The status could not be changed.')
      }
    } finally {
      setBusy(false)
    }
  }

  function choose(status: string) {
    if (status === shown) return
    if (note.type === 'task' && status === 'done') {
      setEvidence('')
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
            type="button"
            disabled={busy}
            aria-label={`Status: ${shown ?? 'N/A'}. Change status of ${note.title}`}
            className="inline-flex h-8 cursor-pointer items-center gap-1 rounded-btn px-1.5 hover:bg-inset disabled:opacity-60 max-rail:min-h-11"
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
        <DialogContent showCloseButton={false}>
          <form
            className="flex flex-col gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              setAskEvidence(false)
              void change('done', evidence.trim())
            }}
          >
            <DialogHeader>
              <DialogTitle className="t-panel font-semibold">Mark as done</DialogTitle>
              <DialogDescription className="t-small text-muted-ink">{note.title}</DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="status-evidence" className="t-caption font-semibold text-muted-ink">
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

import { useId, useState, type FormEvent } from 'react'
import { useApi, useInvalidate } from '@/api/ApiProvider'
import { ApiError } from '@/api/client'
import type { NoteDetail, StandupSection } from '@/api/types'
import { useToast } from '@/components/Toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

/**
 * Appends one line to a section of today's note through the standup append
 * endpoint, sending the hash of the note as shown. A 409 means the note
 * changed in Obsidian: everything reloads and the typed text stays, so
 * nothing is lost.
 */
export function AddLine({ section, note, untouched }: { section: StandupSection; note: NoteDetail; untouched: boolean }) {
  const client = useApi()
  const invalidate = useInvalidate()
  const toast = useToast()
  const inputId = useId()
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!draft.trim() || busy) return
    setBusy(true)
    try {
      // An untouched note is filled with carry-forward first: appending to it as it is would make it "touched",
      // and carry-forward would never run for the day. The append then uses the filled note's hash.
      let target = note
      let filled = false
      if (untouched) {
        const started = await client.startStandup()
        target = started.note
        filled = started.filled
        invalidate()
      }
      const text = draft.trim()
      await client.appendToStandup({ section, text, expected_hash: target.content_hash })
      toast.show(
        filled
          ? `Filled ${target.path} with carry-forward, then appended "${text}" under ${section}`
          : `Added to ## ${section} in ${target.path}`,
      )
      setDraft('')
      invalidate()
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        toast.show(`${note.path} changed in Obsidian, reloaded. Your text is still here; add it again.`)
        invalidate()
      } else {
        toast.show(error instanceof Error ? error.message : 'The line could not be added.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-center gap-2 border-t border-line px-3 py-2">
      <label htmlFor={inputId} className="sr-only">
        Add a line to {section}
      </label>
      <Input id={inputId} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={`Add to ${section}`} className="min-w-0 flex-[1_1_240px]" autoComplete="off" />
      <Button type="submit" variant="secondary" size="sm" disabled={busy || !draft.trim()}>
        Add
      </Button>
    </form>
  )
}

import { useId, useState, type FormEvent } from 'react'
import { useApi, useInvalidate } from '@/api/ApiProvider'
import { Card } from '@/components/Card'
import { useToast } from '@/components/Toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

/** Quick capture: one line becomes a Markdown note in 00-Inbox. Always available, even when the inbox is clear. */
export function CaptureForm() {
  const client = useApi()
  const invalidate = useInvalidate()
  const toast = useToast()
  const id = useId()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const value = text.trim()
    if (!value || busy) return
    setBusy(true)
    try {
      const note = await client.createCapture({ text: value })
      toast.show(`Captured in ${note.path}`)
      setText('')
      invalidate()
    } catch (error) {
      toast.show(error instanceof Error ? error.message : 'The capture could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-3 px-3 py-3">
        <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-1">
          <Label htmlFor={id} className="t-small font-semibold text-muted-ink">
            Quick capture
          </Label>
          <Input id={id} value={text} onChange={(e) => setText(e.target.value)} placeholder="todo: ask infra about the staging database refresh" autoComplete="off" />
        </div>
        <Button type="submit" disabled={busy || !text.trim()}>
          Capture
        </Button>
      </form>
    </Card>
  )
}

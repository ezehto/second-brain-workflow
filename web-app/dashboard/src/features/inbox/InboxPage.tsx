import { useCallback, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useApi } from '@/api/ApiProvider'
import { listAllNotes } from '@/api/listAll'
import type { NoteDetail } from '@/api/types'
import { useQuery } from '@/api/useQuery'
import { Card, CardHead } from '@/components/Card'
import { QueryBoundary } from '@/components/QueryBoundary'
import { useToday } from '@/lib/clock'
import { useProjectContext } from '@/lib/projectContext'
import { noteHref } from '@/lib/routes'
import { NoteReader } from '@/features/notes/NoteReader'
import { SplitPane } from '@/features/notes/SplitPane'
import { useSplitLayout } from '@/features/notes/useMediaQuery'
import { CaptureForm } from './CaptureForm'
import { HandledList, type Handled } from './HandledList'
import { InboxRow } from './InboxRow'

/**
 * The Inbox page: captures with `status: inbox`, newest first (capture names
 * start with their date and time), each read in full because the row needs the
 * text, the classification `/triage` may have written and the hash to send
 * with a write. Selecting a row opens the note in a split pane from 1024 up
 * (the `note` query parameter, as on Tasks), or on the note route below that.
 */
export function InboxPage() {
  const client = useApi()
  const today = useToday()
  const navigate = useNavigate()
  const project = useProjectContext()
  const split = useSplitLayout()
  const [params, setParams] = useSearchParams()
  const [handled, setHandled] = useState<Handled[]>([])
  const selectedPath = params.get('note') ?? undefined

  const captures = useQuery(
    useCallback(async () => {
      const summaries = await listAllNotes(client, { type: 'capture', status: ['inbox'], ordering: '-path' })
      return Promise.all(summaries.map((s) => client.lookupNote({ path: s.path })))
    }, [client]),
  )

  // A capture can change status in Obsidian between the list and the read; the list is the rule.
  const inbox = useMemo(() => (captures.status === 'success' ? captures.data.filter((c) => c.status === 'inbox') : []), [captures])

  const select = (note: NoteDetail) => {
    if (!split) return navigate(noteHref(note.path))
    setParams(selectedPath === note.path ? {} : { note: note.path })
  }

  const reader = split && selectedPath ? <NoteReader path={selectedPath} onClose={() => setParams({})} /> : undefined

  return (
    <div className="flex flex-col gap-4">
      <CaptureForm />
      <SplitPane
        reader={reader}
        readerLabel="Open note"
        list={
          <div className="flex flex-col gap-4">
            <Card>
              <CardHead title="Awaiting triage" count={captures.status === 'success' ? inbox.length : undefined} />
              <QueryBoundary
                query={captures}
                rows={4}
                isEmpty={() => inbox.length === 0}
                empty={
                  <>
                    Inbox clear. Capture a thought above, or add a note to 00-Inbox in Obsidian.
                    {project && <span className="t-caption mt-1 block">Captures belong to no project, so the project filter does not apply here.</span>}
                  </>
                }
              >
                {() => (
                  <ul aria-label="Captures awaiting triage" className="m-0 p-0">
                    {inbox.map((note, i) => (
                      <InboxRow
                        key={note.path}
                        note={note}
                        today={today}
                        active={i === 0}
                        selected={note.path === selectedPath}
                        onSelect={select}
                        onHandled={(item) => setHandled((h) => [item, ...h])}
                      />
                    ))}
                  </ul>
                )}
              </QueryBoundary>
            </Card>
            <HandledList items={handled} />
          </div>
        }
      />
    </div>
  )
}

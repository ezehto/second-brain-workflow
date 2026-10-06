import { useCallback } from 'react'
import { useApi } from '@/api/ApiProvider'
import { listAllNotes } from '@/api/listAll'
import { useQuery } from '@/api/useQuery'
import type { NoteSummary } from '@/api/types'
import { Card, CardHead } from '@/components/Card'
import { QueryBoundary } from '@/components/QueryBoundary'
import { StatusMenu } from '@/components/StatusMenu'
import { useToday } from '@/lib/clock'
import { formatWhen } from '@/lib/dates'
import { NoteRow } from './NoteRow'

interface Opening {
  selectedPath?: string
  onOpen?: (note: NoteSummary) => void
}

const PROPOSED_FIRST = ['proposed', 'accepted', 'superseded', 'rejected']

/** The project's decisions, proposed first, each opening the reader. */
export function DecisionsTab({ decisions, selectedPath, onOpen }: { decisions: NoteSummary[] } & Opening) {
  const sorted = [...decisions].sort(
    (a, b) =>
      PROPOSED_FIRST.indexOf(a.status ?? '') - PROPOSED_FIRST.indexOf(b.status ?? '') || b.modified.localeCompare(a.modified) || a.title.localeCompare(b.title),
  )
  return (
    <Card>
      <CardHead title="Decisions" count={decisions.length} />
      {sorted.length === 0 ? (
        <p className="m-0 border-t border-line px-3 py-3 text-muted-ink">No decisions recorded for this project. Use New in the header to add one.</p>
      ) : (
        <ul className="m-0 list-none p-0">
          {sorted.map((d) => (
            <li key={d.path}>
              <NoteRow note={d} selected={d.path === selectedPath} onOpen={onOpen} meta={d.decided ? `Decided ${d.decided}` : undefined} status={<StatusMenu note={d} />} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

/** Every other note of the project (lessons, documents, daily mentions), newest first. */
export function NotesTab({ slug, selectedPath, onOpen }: { slug: string } & Opening) {
  const client = useApi()
  const today = useToday()
  const notes = useQuery(useCallback(() => listAllNotes(client, { project: slug, ordering: '-modified' }), [client, slug]))
  return (
    <Card>
      <CardHead title="Notes" count={notes.status === 'success' ? notes.data.filter(isPlainNote).length : undefined} />
      <QueryBoundary query={notes} isEmpty={(all) => all.filter(isPlainNote).length === 0} empty="No other notes for this project yet. Add a note with this project in its frontmatter.">
        {(all) => (
          <ul className="m-0 list-none p-0">
            {all.filter(isPlainNote).map((n) => (
              <li key={n.path}>
                <NoteRow note={n} selected={n.path === selectedPath} onOpen={onOpen} meta={`${n.type}, ${formatWhen(n.modified, today)}`} />
              </li>
            ))}
          </ul>
        )}
      </QueryBoundary>
    </Card>
  )
}

/** Tasks, decisions and the project note itself have their own places. */
const isPlainNote = (n: NoteSummary) => n.type !== 'task' && n.type !== 'decision' && n.type !== 'project'

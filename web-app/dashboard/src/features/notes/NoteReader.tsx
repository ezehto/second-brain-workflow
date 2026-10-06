import { useCallback, useId, useMemo, type ReactNode } from 'react'
import { Link } from 'react-router'
import { useApi } from '@/api/ApiProvider'
import { useQuery } from '@/api/useQuery'
import type { NoteDetail } from '@/api/types'
import { Card } from '@/components/Card'
import { Icon } from '@/components/Icon'
import { PriorityMark } from '@/components/PriorityMark'
import { QueryBoundary } from '@/components/QueryBoundary'
import { StatusChip } from '@/components/StatusChip'
import { StatusMenu } from '@/components/StatusMenu'
import { Button } from '@/components/ui/button'
import { isOverdue } from '@/domain/tasks'
import { projectLookup } from '@/domain/projects'
import { useToday } from '@/lib/clock'
import { NOT_AVAILABLE, formatShortDate, wallTime } from '@/lib/dates'
import { noteHref, projectHref } from '@/lib/routes'
import { NoteMarkdown } from './NoteMarkdown'

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col">
      <dt className="t-caption text-muted-ink">{label}</dt>
      <dd className="t-body m-0 min-w-0 truncate">{children}</dd>
    </div>
  )
}

const stamp = (iso: string | null) => (iso ? `${formatShortDate(iso)}${iso.length > 10 ? `, ${wallTime(iso)}` : ''}` : NOT_AVAILABLE)

function Loaded({ note, onClose }: { note: NoteDetail; onClose?: () => void }) {
  const client = useApi()
  const today = useToday()
  const titleId = useId()
  const projects = useQuery(useCallback(() => client.listProjects(), [client]))
  const lookup = useMemo(() => projectLookup(projects.status === 'success' ? projects.data : undefined), [projects])
  const overdue = isOverdue(note, today)

  return (
    <article aria-labelledby={titleId} className="flex flex-col">
      <header className="flex flex-col gap-2 border-b border-line px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <h2 id={titleId} className="t-panel min-w-0 break-words">
            {note.title}
          </h2>
          {onClose && (
            <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close note">
              <Icon name="close" />
            </Button>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="t-small rounded-full bg-inset px-2 py-px font-semibold text-muted-ink">{note.type}</span>
          {note.parse_error ? <StatusChip status={note.status} /> : <StatusMenu note={note} contentHash={note.content_hash} />}
        </div>
      </header>

      {note.parse_error && (
        <div role="alert" className="t-body border-b border-line bg-tint-blocked px-4 py-2 text-status-blocked">
          <span className="font-semibold">This note has a parse error.</span> {note.parse_error} Fix it in Obsidian; its status cannot be changed here.
        </div>
      )}

      <dl className="m-0 grid grid-cols-2 gap-x-4 gap-y-2 border-b border-line px-4 py-3 sm:grid-cols-3">
        <Field label="Priority">{note.priority ? <PriorityMark priority={note.priority} /> : NOT_AVAILABLE}</Field>
        <Field label="Due">
          <span className={overdue ? 'font-semibold text-status-blocked' : undefined}>
            {note.due ? (overdue ? `Overdue, ${formatShortDate(note.due)}` : formatShortDate(note.due)) : NOT_AVAILABLE}
          </span>
        </Field>
        <Field label="Project">
          {note.project && lookup.known(note.project) ? <Link to={projectHref(note.project)}>{lookup.title(note.project)}</Link> : lookup.title(note.project)}
        </Field>
        <Field label="Created">{stamp(note.created)}</Field>
        <Field label="Modified">{stamp(note.modified)}</Field>
        <Field label="Tags">{note.tags.length ? note.tags.join(', ') : NOT_AVAILABLE}</Field>
        <div className="col-span-full min-w-0">
          <dt className="t-caption text-muted-ink">Path</dt>
          <dd className="mono m-0 break-all text-muted-ink">{note.path}</dd>
        </div>
      </dl>

      <div className="px-4 py-3">
        {note.body.trim() ? <NoteMarkdown body={note.body} links={note.links} /> : <p className="t-body m-0 text-muted-ink">This note has no body yet.</p>}
      </div>

      <section aria-label="Backlinks" className="border-t border-line px-4 py-3">
        <h3 className="t-body font-semibold">
          Backlinks <span className="num t-caption font-normal text-muted-ink">{note.backlinks.length}</span>
        </h3>
        {note.backlinks.length ? (
          <ul className="m-0 mt-1 list-none p-0">
            {note.backlinks.map((link) => (
              <li key={link.path} className="t-body py-0.5">
                <Link to={noteHref(link.path)}>{link.title}</Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="t-small m-0 mt-1 text-muted-ink">No other note links here.</p>
        )}
      </section>
    </article>
  )
}

/**
 * One note in full: metadata, status control, rendered body, backlinks and
 * parse errors. Reused by every page that lists notes, in a split pane or as
 * the `/notes?path=` route. It fetches the note itself through `lookupNote`,
 * so the `content_hash` it hands the status menu is the one on screen; a write
 * anywhere refetches it.
 */
export function NoteReader({ path, onClose }: { path: string; onClose?: () => void }) {
  const client = useApi()
  const note = useQuery(useCallback(() => client.lookupNote({ path }), [client, path]))
  return (
    <Card className={note.status === 'success' ? undefined : 'pt-3'}>
      <QueryBoundary query={note} rows={6}>
        {(data) => <Loaded note={data} onClose={onClose} />}
      </QueryBoundary>
    </Card>
  )
}

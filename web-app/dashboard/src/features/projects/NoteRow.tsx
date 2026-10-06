import type { ReactNode } from 'react'
import { Link } from 'react-router'
import type { NoteSummary } from '@/api/types'
import { CardRow } from '@/components/Card'
import { cn } from '@/lib/utils'
import { useProjectHref } from '@/lib/projectContext'

/**
 * One note as a ruled row: the title is a link to the note. With `onOpen` a
 * plain click opens the note in a split pane instead (a modified click still
 * follows the link), as `TaskRow` does.
 */
export function NoteRow({
  note,
  meta,
  status,
  selected,
  onOpen,
}: {
  note: NoteSummary
  /** Quiet text after the title: type, date. */
  meta?: ReactNode
  /** Right-hand slot, a chip or a `StatusMenu`. */
  status?: ReactNode
  selected?: boolean
  onOpen?: (note: NoteSummary) => void
}) {
  const href = useProjectHref()
  return (
    <CardRow aria-current={selected ? 'true' : undefined} className={cn('grid-cols-[minmax(0,1fr)_auto]', selected && 'bg-inset')}>
      <div className="flex min-w-0 items-baseline gap-2">
        <Link
          to={href.note(note.path)}
          className="linkbtn t-body truncate"
          onClick={(event) => {
            if (!onOpen || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
            event.preventDefault()
            onOpen(note)
          }}
        >
          {note.title}
        </Link>
        {meta && <span className="num t-caption flex-none text-muted-ink">{meta}</span>}
      </div>
      {status ?? <span />}
    </CardRow>
  )
}

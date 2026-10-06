import type { ReactNode } from 'react'
import { Link } from 'react-router'
import type { NoteSummary } from '@/api/types'
import { CardRow } from '@/components/Card'
import { noteHref } from '@/lib/routes'
import { cn } from '@/lib/utils'

/** A note title as a link: a plain click calls `onOpen` (split pane), a modified click still follows the link. */
export function NoteLink({ note, onOpen }: { note: NoteSummary; onOpen?: (note: NoteSummary) => void }) {
  return (
    <Link
      to={noteHref(note.path)}
      className="linkbtn t-body truncate"
      onClick={(event) => {
        if (!onOpen || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
        event.preventDefault()
        onOpen(note)
      }}
    >
      {note.title}
    </Link>
  )
}

/**
 * A dense (32px) row with a lead slot, the title, columns on a wide list, and
 * a trailing slot. `stacked` (a phone, or a list narrowed by the reader)
 * makes it two lines of 48px: the columns move under the title.
 */
export function ListRow({
  lead,
  title,
  columns,
  trail,
  stacked,
  selected,
  template,
}: {
  lead?: ReactNode
  title: ReactNode
  /** Cell nodes, in the order of `template`'s middle tracks. */
  columns: ReactNode[]
  trail?: ReactNode
  stacked: boolean
  selected: boolean
  /** Grid tracks for the wide layout, without the lead and trail. */
  template: string
}) {
  const tracks = [lead ? 'auto' : null, template, trail ? 'auto' : null].filter(Boolean).join(' ')
  return (
    <CardRow
      lines={stacked ? 2 : 1}
      aria-current={selected ? 'true' : undefined}
      className={cn(!stacked && 'min-h-8 py-0', selected && 'bg-inset')}
      style={stacked ? { gridTemplateColumns: [lead ? 'auto' : null, 'minmax(0,1fr)', trail ? 'auto' : null].filter(Boolean).join(' ') } : { gridTemplateColumns: tracks }}
    >
      {lead}
      {stacked ? (
        <div className="flex min-w-0 flex-col">
          {title}
          <span className="t-small flex min-w-0 gap-2 truncate text-muted-ink">{columns}</span>
        </div>
      ) : (
        <>
          {title}
          {columns}
        </>
      )}
      {trail}
    </CardRow>
  )
}

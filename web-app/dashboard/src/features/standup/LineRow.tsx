import { Link } from 'react-router'
import { CardRow } from '@/components/Card'
import { StatusChip } from '@/components/StatusChip'
import { textSegments, type DailyLine } from '@/domain/daily'
import { cn } from '@/lib/utils'
import type { LinkResolver } from './links'

/** A line's text with each wikilink linked to its note or project; an unresolved link stays text. */
export function LineText({ line, resolver }: { line: DailyLine; resolver: LinkResolver }) {
  return (
    <>
      {textSegments(line.text).map((seg, i) => {
        if (seg.kind === 'text') return <span key={i}>{seg.value}</span>
        const target = resolver.resolve(seg.target)
        return target ? (
          <Link key={i} to={target.href} className="linkbtn">
            {seg.label}
          </Link>
        ) : (
          <span key={i} title="No note with this name">
            {seg.label}
          </span>
        )
      })}
    </>
  )
}

/** The checkbox as a read-only mark. The word is for screen readers; the box is not the only signal. */
function Box({ checked }: { checked: boolean | null }) {
  if (checked === null) return <span aria-hidden="true" />
  return (
    <span
      role="img"
      aria-label={checked ? 'Done' : 'Not done'}
      className={cn('inline-flex size-4 items-center justify-center rounded-[4px] border', checked ? 'border-status-done bg-tint-done text-status-done' : 'border-faint')}
    >
      {checked && (
        <svg viewBox="0 0 24 24" className="size-3" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M5 12.5l4.5 4.5L19 7" />
        </svg>
      )}
    </span>
  )
}

/** One list line of a section as a ruled row. `carried` is how many standups in a row list it (shown from 2). */
export function LineRow({ line, resolver, carried }: { line: DailyLine; resolver: LinkResolver; carried?: number }) {
  return (
    <CardRow className="grid-cols-[1rem_minmax(0,1fr)_auto]">
      <Box checked={line.checked} />
      <span className="t-body min-w-0 break-words">
        <LineText line={line} resolver={resolver} />
      </span>
      {carried !== undefined && carried >= 2 && <StatusChip label={`In Today for ${carried} days`} tone={carried >= 3 ? 'risk' : 'neutral'} />}
    </CardRow>
  )
}

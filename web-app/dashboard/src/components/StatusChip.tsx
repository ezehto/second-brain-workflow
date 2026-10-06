import { cn } from '@/lib/utils'
import { NOT_AVAILABLE } from '@/lib/dates'
import { statusTone, TONE_TEXT, type StatusTone } from '@/domain/status'

/**
 * A status as a coloured dot and its word. Colour is never the only signal:
 * the word is always rendered. Pass `tone` to override the colour a status
 * word would get (project health uses its own words, and an overdue date uses
 * `blocked` with the word "Overdue").
 *
 * Only blocked and overdue get a tinted background, because they are the two
 * states that ask for action; every other status is a dot and a word on the
 * surface it sits on. Inside an `AccentCard` the chip takes the inset surface
 * back, since coloured text cannot sit on the violet fill.
 */
export function StatusChip({
  status,
  label,
  tone,
  className,
}: {
  status?: string | null
  label?: string
  tone?: StatusTone
  className?: string
}) {
  const word = label ?? status ?? NOT_AVAILABLE
  const resolved = tone ?? statusTone(status)
  const tinted = resolved === 'blocked'
  return (
    <span
      className={cn(
        't-caption inline-flex h-6 items-center gap-1.5 rounded-full font-semibold whitespace-nowrap',
        TONE_TEXT[resolved],
        tinted ? 'bg-tint-blocked px-2.5' : 'bg-transparent px-0',
        'in-data-[accent]:bg-inset in-data-[accent]:px-2.5',
        className,
      )}
    >
      <span aria-hidden="true" className="size-[7px] flex-none rounded-full bg-current" />
      {word}
    </span>
  )
}

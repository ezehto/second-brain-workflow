import { cn } from '@/lib/utils'
import { NOT_AVAILABLE } from '@/lib/dates'
import { statusTone, TONE_TEXT, type StatusTone } from '@/domain/status'

/**
 * A status as a coloured dot and its word. Colour is never the only signal:
 * the word is always rendered. Pass `tone` to override the colour a status
 * word would get (project health uses its own words).
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
  const colour = TONE_TEXT[tone ?? statusTone(status)]
  return (
    <span
      className={cn(
        'inline-flex h-6 items-center gap-1.5 rounded-full bg-inset px-2.5 text-xs font-semibold whitespace-nowrap',
        colour,
        className,
      )}
    >
      <span aria-hidden="true" className="size-[7px] flex-none rounded-full bg-current" />
      {word}
    </span>
  )
}

import { Link } from 'react-router'
import { cn } from '@/lib/utils'

export interface SegmentedOption<V extends string = string> {
  value: V
  label: string
  /** Renders a link instead of a button (the context switcher). */
  href?: string
}

const SEG =
  'inline-flex min-h-8 items-center rounded-full border-0 bg-transparent px-3 t-small font-semibold text-muted-ink no-underline hover:bg-line hover:text-ink max-rail:min-h-11'
const SEG_ON = 'bg-brand-fill text-white hover:bg-brand-fill hover:text-white'

/**
 * Pill toggle group for filters and grouping. A real group of buttons with
 * `aria-pressed`; use the shadcn Tabs component when there are tab panels.
 */
export function Segmented<V extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: SegmentedOption<V>[]
  value: V
  onChange?: (value: V) => void
  label: string
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex flex-wrap gap-1 rounded-full bg-inset p-0.5">
      {options.map((o) => {
        const on = o.value === value
        if (o.href && !on) {
          return (
            <Link key={o.value} to={o.href} className={SEG}>
              {o.label}
            </Link>
          )
        }
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={on}
            aria-current={on && o.href ? 'true' : undefined}
            onClick={() => onChange?.(o.value)}
            className={cn(SEG, 'cursor-pointer', on && SEG_ON, on && o.href && 'cursor-default')}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

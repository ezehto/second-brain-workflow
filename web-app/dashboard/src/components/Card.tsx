import type { ComponentProps, ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** The standard rounded card. A page is a grid of these. */
export function Card({ className, ...props }: ComponentProps<'section'>) {
  return <section className={cn('min-w-0 rounded-card border border-line bg-surface', className)} {...props} />
}

/**
 * The one filled card a page may have, for its single most important thing
 * (Today's focus on the dashboard). Never use more than one per page.
 */
export function AccentCard({ className, ...props }: ComponentProps<'section'>) {
  return (
    <section
      data-accent
      className={cn(
        'min-w-0 rounded-card border border-brand-fill bg-brand-fill text-white [&_.note]:text-brand-on-fill',
        className,
      )}
      {...props}
    />
  )
}

/**
 * Panel heading: 40px high, the h2 with an optional count beside it (a count,
 * not a subtitle), and right-aligned actions. `note` is a legacy quiet caption;
 * new code uses `PreviewBadge` for later-phase data instead.
 */
export function CardHead({
  title,
  count,
  note,
  children,
  className,
}: {
  title: string
  /** Number of rows in the panel, shown as a quiet caption next to the title. */
  count?: number | string
  note?: string
  children?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex min-h-10 flex-wrap items-center justify-between gap-x-3 gap-y-1 px-3 py-1', className)}>
      <div className="flex min-w-0 items-baseline gap-2">
        <h2 className="t-panel font-semibold">{title}</h2>
        {count !== undefined && <span className={cn('num text-muted-ink', typeof count === 'number' ? 't-numeral' : 't-caption')}>{count}</span>}
      </div>
      {(note || children) && (
        <div className="flex flex-wrap items-center gap-2">
          {note && <span className="note">{note}</span>}
          {children}
        </div>
      )}
    </div>
  )
}

/**
 * A ruled row inside a panel: 36px for one line, 48px for two (`lines`),
 * 12px side padding. Taller content grows the row, never clips it.
 */
export function CardRow({ className, lines = 1, ...props }: ComponentProps<'div'> & { lines?: 1 | 2 }) {
  return (
    <div
      className={cn('grid items-center gap-3 border-t border-line px-3 py-1', lines === 2 ? 'min-h-12' : 'min-h-9', className)}
      {...props}
    />
  )
}

/** A tile nested in a card, on the inset colour. */
export function InsetItem({ className, ...props }: ComponentProps<'div'>) {
  return <div className={cn('rounded-tile bg-inset p-3', className)} {...props} />
}

/** Quiet footnote at the foot of a card, for a stated rule or a source. */
export function CardFootnote({ children, accent }: { children: ReactNode; accent?: boolean }) {
  return <p className={cn('note m-0 border-t px-3 py-2', accent ? 'border-white/20' : 'border-line')}>{children}</p>
}

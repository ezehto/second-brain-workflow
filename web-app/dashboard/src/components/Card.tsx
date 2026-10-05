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

/** Card heading: the h2, an optional quiet note, and right-aligned actions. */
export function CardHead({
  title,
  note,
  children,
  className,
}: {
  title: string
  /** Source or phase note, shown quietly beside the actions. */
  note?: string
  children?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-wrap items-center justify-between gap-3 px-5 pt-4 pb-3', className)}>
      <h2 className="text-base">{title}</h2>
      {(note || children) && (
        <div className="flex flex-wrap items-center gap-3">
          {note && <span className="note">{note}</span>}
          {children}
        </div>
      )}
    </div>
  )
}

/** A ruled row inside a card. */
export function CardRow({ className, ...props }: ComponentProps<'div'>) {
  return <div className={cn('grid items-center gap-3 border-t border-line px-5 py-[11px]', className)} {...props} />
}

/** A tile nested in a card, on the inset colour. */
export function InsetItem({ className, ...props }: ComponentProps<'div'>) {
  return <div className={cn('rounded-tile bg-inset p-3.5', className)} {...props} />
}

/** Quiet footnote at the foot of a card, for a stated rule or a source. */
export function CardFootnote({ children, accent }: { children: ReactNode; accent?: boolean }) {
  return <p className={cn('note m-0 border-t px-5 pt-3 pb-4', accent ? 'border-white/20' : 'border-line')}>{children}</p>
}

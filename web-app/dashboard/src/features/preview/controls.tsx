import type { ComponentProps, ReactNode } from 'react'
import { PreviewBadge } from '@/components/PreviewBadge'
import { cn } from '@/lib/utils'

/** The one banner a preview page carries: the badge, the phase, and that the data is sample data. */
export function PreviewBanner({ phase, what, source }: { phase: string; what: string; source: string }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-card border border-line bg-surface px-3 py-2">
      <PreviewBadge detail={source} />
      <p className="t-small m-0 text-muted-ink">
        <strong className="font-semibold text-ink">{phase}.</strong> {what} The data on this page is sample data; nothing is read from your vault yet.
      </p>
    </div>
  )
}

/** A native select with a visible label. Native keeps it keyboard, touch and screen reader friendly. */
export function LabelledSelect({
  label,
  id,
  className,
  children,
  ...props
}: { label: string; id: string; children: ReactNode } & ComponentProps<'select'>) {
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="t-small text-muted-ink">
        {label}
      </label>
      <select
        id={id}
        className={cn(
          't-small h-8 max-w-52 cursor-pointer rounded-btn border border-line bg-inset px-2 text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand max-rail:min-h-11',
          className,
        )}
        {...props}
      >
        {children}
      </select>
    </div>
  )
}

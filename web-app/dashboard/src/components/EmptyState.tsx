import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** Says what is empty and, when there is something to do, what to do. */
export function EmptyState({ children, action, className }: { children: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn('flex flex-col items-start gap-2.5 px-5 pb-5 text-muted-ink', className)}>
      <p className="m-0">{children}</p>
      {action}
    </div>
  )
}

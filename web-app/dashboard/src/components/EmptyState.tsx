import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** Says what is empty and, when there is something to do, what to do. */
export function EmptyState({ children, action, className }: { children: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn('flex flex-col items-start gap-2 px-3 pb-3 text-muted-ink', className)}>
      <p className="m-0">{children}</p>
      {action}
    </div>
  )
}

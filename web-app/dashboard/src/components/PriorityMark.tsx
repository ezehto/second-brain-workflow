import { cn } from '@/lib/utils'
import { NOT_AVAILABLE } from '@/lib/dates'

const MARKS: Record<string, { mark: string; word: string; style: string }> = {
  high: { mark: 'P1', word: 'High priority', style: 'font-bold text-ink' },
  medium: { mark: 'P2', word: 'Medium priority', style: 'font-medium text-ink' },
  low: { mark: 'P3', word: 'Low priority', style: 'font-normal text-muted-ink' },
}

/**
 * Priority as P1, P2 or P3 (high, medium, low), told apart by weight and not
 * by colour, so red stays reserved for blocked and overdue. A missing or
 * unrecognised priority shows `N/A`.
 */
export function PriorityMark({ priority, className }: { priority: string | null | undefined; className?: string }) {
  const entry = priority ? MARKS[priority] : undefined
  return (
    <span className={cn('num t-caption inline-block min-w-7', entry?.style ?? 'font-normal text-muted-ink', className)}>
      <span aria-hidden="true">{entry?.mark ?? NOT_AVAILABLE}</span>
      <span className="sr-only">{entry?.word ?? 'No priority'}</span>
    </span>
  )
}

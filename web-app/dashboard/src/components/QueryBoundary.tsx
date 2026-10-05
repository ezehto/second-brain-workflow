import type { ReactNode } from 'react'
import type { Query } from '@/api/useQuery'
import { ErrorState } from './ErrorState'
import { EmptyState } from './EmptyState'

/** Skeleton rows while a section loads. Announced once, not per row. */
export function LoadingRows({ rows = 3 }: { rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-3 px-5 pb-5">
      <span className="sr-only">Loading</span>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} aria-hidden="true" className="h-4 animate-pulse rounded-full bg-inset" style={{ width: `${88 - i * 14}%` }} />
      ))}
    </div>
  )
}

/**
 * Renders the loading, error, empty or loaded state of one query. `isEmpty`
 * decides emptiness from the data; `empty` is what to say when it is.
 */
export function QueryBoundary<T>({
  query,
  isEmpty,
  empty,
  rows,
  children,
}: {
  query: Query<T>
  isEmpty?: (data: T) => boolean
  empty?: ReactNode
  rows?: number
  children: (data: T) => ReactNode
}) {
  if (query.status === 'loading') return <LoadingRows rows={rows} />
  if (query.status === 'error') return <ErrorState message={query.error.message} onRetry={query.refetch} />
  if (isEmpty?.(query.data)) return <EmptyState>{empty}</EmptyState>
  return <>{children(query.data)}</>
}

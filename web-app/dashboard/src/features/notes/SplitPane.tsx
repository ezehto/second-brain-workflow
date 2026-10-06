import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/**
 * A list with an optional reader beside it. With no `reader` the list takes
 * the full width; with one, the list is 5/12 and the reader 7/12 from the
 * split width up (1024). The reader stays in view while the list scrolls.
 *
 * Below the split width the pane is not shown: the page sends a selection to
 * the `/notes?path=` route instead (see `useSplitLayout`), so the reader never
 * squeezes a phone-width list.
 */
export function SplitPane({ list, reader, readerLabel = 'Note' }: { list: ReactNode; reader?: ReactNode; readerLabel?: string }) {
  return (
    <div className={cn('grid grid-cols-1 items-start gap-4', reader ? 'lg:grid-cols-[5fr_7fr]' : undefined)}>
      <div className="min-w-0">{list}</div>
      {reader && (
        <aside aria-label={readerLabel} className="hidden min-w-0 lg:sticky lg:top-4 lg:block lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto">
          {reader}
        </aside>
      )}
    </div>
  )
}

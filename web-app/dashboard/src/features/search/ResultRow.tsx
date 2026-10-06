import { Link } from 'react-router'
import type { SearchResult } from '@/api/types'
import { withProject } from '@/lib/projectContext'
import { noteHref } from '@/lib/routes'
import { cn } from '@/lib/utils'
import { Highlight } from './Highlight'

/**
 * One search result: type chip, title, snippet with the match marked, project,
 * path and where it came from. With `onSelect` (a wide screen) the title opens
 * the note in the split pane; without it the title links to the reader route.
 */
export function ResultRow({
  result,
  query,
  project,
  context,
  selected,
  onSelect,
}: {
  result: SearchResult
  query: string
  /** The note's project title, or null when it has none or is not known yet. */
  project: string | null
  context: string | null
  selected: boolean
  onSelect?: (path: string) => void
}) {
  const titleClass = 'min-w-0 break-words text-left font-semibold text-ink underline-offset-2 hover:underline'
  return (
    <li className={cn('flex flex-col gap-1 border-b border-line px-3 py-3 last:border-b-0', selected && 'bg-inset')}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="t-small rounded-full bg-inset px-2 py-px font-semibold text-muted-ink">{result.type}</span>
        {onSelect ? (
          <button type="button" aria-current={selected ? 'true' : undefined} onClick={() => onSelect(result.path)} className={cn(titleClass, 'cursor-pointer border-0 bg-transparent p-0 t-body')}>
            {result.title}
          </button>
        ) : (
          <Link to={withProject(noteHref(result.path), context)} className={cn(titleClass, 't-body')}>
            {result.title}
          </Link>
        )}
      </div>
      <p className="t-body m-0 text-muted-ink">
        <Highlight text={result.snippet} query={query} />
      </p>
      <p className="t-small m-0 flex flex-wrap items-center gap-x-3 text-muted-ink">
        {project && <span>{project}</span>}
        <span className="mono min-w-0 break-all">{result.path}</span>
        <span>source: {result.source}</span>
      </p>
    </li>
  )
}

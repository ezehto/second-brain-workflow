import { useCallback, useEffect, useId, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react'
import { useNavigate } from 'react-router'
import { useApi } from '@/api/ApiProvider'
import type { SearchResult } from '@/api/types'
import { useQuery } from '@/api/useQuery'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { useDebouncedValue } from '@/features/search/useDebouncedValue'
import { useProjectContext, withProject } from '@/lib/projectContext'
import { noteHref } from '@/lib/routes'
import { cn } from '@/lib/utils'
import { Icon, type IconName } from './Icon'
import { NAV_GROUPS } from './nav'
import { useQuickActions, type QuickActionKind } from './QuickActions'

/**
 * Ctrl+K (Cmd+K on a Mac) calls `onOpen` and stops the browser's own handling.
 * The shell passes a callback that opens the palette.
 */
export function useCommandPaletteShortcut(onOpen: () => void) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        onOpen()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onOpen])
}

export const PALETTE_DEBOUNCE_MS = 200
const NOTE_LIMIT = 8

const CREATE: { kind: QuickActionKind; label: string }[] = [
  { kind: 'task', label: 'New task' },
  { kind: 'capture', label: 'New capture' },
  { kind: 'followup', label: 'New follow-up' },
  { kind: 'decision', label: 'New decision' },
  { kind: 'lesson', label: 'New note' },
]

type Entry =
  | { id: string; group: 'go'; label: string; icon: IconName; go: { to: string } | { action: QuickActionKind } }
  | { id: string; group: 'note'; label: string; result: SearchResult }

const DESTINATIONS = NAV_GROUPS.flatMap((g) => g.items)

/** The command palette: jump to a page, start a quick action, or open a note. */
export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  // The dialog has no trigger element, so Radix cannot hand focus back: remember where it was and restore it.
  // Closing for a quick action must not: the action's own dialog takes focus.
  const returnTo = useRef<HTMLElement | null>(null)
  const keepFocus = useRef(false)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="top-[20%] translate-y-0 gap-0 p-0 sm:max-w-xl"
        onOpenAutoFocus={() => {
          returnTo.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
        }}
        onCloseAutoFocus={(e) => {
          e.preventDefault()
          if (!keepFocus.current && returnTo.current?.isConnected) returnTo.current.focus()
          keepFocus.current = false
        }}
      >
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <DialogDescription className="sr-only">Type to jump to a page, start a quick action or open a note.</DialogDescription>
        <PaletteBody
          onClose={() => onOpenChange(false)}
          onAction={() => {
            keepFocus.current = true
          }}
        />
      </DialogContent>
    </Dialog>
  )
}

function PaletteBody({ onClose, onAction }: { onClose: () => void; onAction: () => void }) {
  const client = useApi()
  const navigate = useNavigate()
  const project = useProjectContext()
  const quick = useQuickActions()
  const listId = useId()
  const [text, setText] = useState('')
  const [active, setActive] = useState(0)
  const q = text.trim()
  const debounced = useDebouncedValue(q, PALETTE_DEBOUNCE_MS)

  const search = useQuery(
    useCallback(async (): Promise<SearchResult[]> => (debounced ? (await client.search(debounced)).results.slice(0, NOTE_LIMIT) : []), [client, debounced]),
  )

  const entries = useMemo<Entry[]>(() => {
    const needle = q.toLowerCase()
    const go: Entry[] = [
      ...DESTINATIONS.map<Entry>((d) => ({ id: `go-${d.to}`, group: 'go', label: d.label, icon: d.icon, go: { to: d.to } })),
      ...CREATE.map<Entry>((c) => ({ id: `new-${c.kind}`, group: 'go', label: c.label, icon: 'plus', go: { action: c.kind } })),
    ].filter((e) => e.label.toLowerCase().includes(needle))
    // Results of an older word are not shown against a newer one.
    const notes: Entry[] =
      search.status === 'success' && debounced === q
        ? search.data.map((r) => ({ id: `note-${r.path}`, group: 'note', label: r.title, result: r }))
        : []
    return [...go, ...notes]
  }, [q, debounced, search])

  const safeActive = Math.min(active, Math.max(entries.length - 1, 0))

  function choose(entry: Entry) {
    if (entry.group === 'note') {
      onClose()
      navigate(withProject(noteHref(entry.result.path), project))
    } else if ('to' in entry.go) {
      onClose()
      navigate(withProject(entry.go.to, project))
    } else {
      onAction()
      onClose()
      quick.open(entry.go.action)
    }
  }

  function onKeyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      if (!entries.length) return
      setActive((safeActive + (event.key === 'ArrowDown' ? 1 : -1) + entries.length) % entries.length)
    } else if (event.key === 'Enter') {
      event.preventDefault()
      const entry = entries[safeActive]
      if (entry) choose(entry)
    }
  }

  const goEntries = entries.filter((e) => e.group === 'go')
  const noteEntries = entries.filter((e) => e.group === 'note')
  const searching = !!q && (debounced !== q || search.status === 'loading')

  const option = (entry: Entry) => {
    const index = entries.indexOf(entry)
    const on = index === safeActive
    return (
      <li
        key={entry.id}
        id={`${listId}-${entry.id}`}
        role="option"
        aria-selected={on}
        onMouseMove={() => setActive(index)}
        onClick={() => choose(entry)}
        className={cn('flex min-h-9 cursor-pointer items-center gap-3 px-3 py-1.5 t-body', on ? 'bg-inset text-ink' : 'text-muted-ink')}
      >
        {entry.group === 'go' ? (
          <>
            <Icon name={entry.icon} className="size-4 flex-none" />
            <span className="min-w-0 flex-1 truncate">{entry.label}</span>
          </>
        ) : (
          <>
            <span className="t-small flex-none rounded-full bg-line px-2 py-px font-semibold text-muted-ink">{entry.result.type}</span>
            <span className="min-w-0 flex-1 truncate">{entry.label}</span>
            <span className="mono hidden max-w-[40%] truncate text-muted-ink sm:inline">{entry.result.path}</span>
          </>
        )}
      </li>
    )
  }

  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-2 border-b border-line px-3">
        <Icon name="search" className="size-4 flex-none text-muted-ink" />
        <label htmlFor={`${listId}-input`} className="sr-only">
          Search commands and notes
        </label>
        <input
          id={`${listId}-input`}
          role="combobox"
          aria-expanded="true"
          aria-controls={`${listId}-list`}
          aria-activedescendant={entries[safeActive] ? `${listId}-${entries[safeActive].id}` : undefined}
          autoComplete="off"
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            setActive(0)
          }}
          onKeyDown={onKeyDown}
          placeholder="Go to a page, start something, or find a note"
          className="t-body h-11 min-w-0 flex-1 border-0 bg-transparent text-ink outline-none placeholder:text-muted-ink"
        />
        <kbd className="t-caption rounded border border-line px-1 font-sans text-muted-ink" aria-hidden="true">
          Esc
        </kbd>
      </div>

      <div id={`${listId}-list`} role="listbox" aria-label="Results" className="max-h-[min(60vh,420px)] overflow-y-auto py-1">
        {goEntries.length > 0 && (
          <div role="group" aria-labelledby={`${listId}-go`}>
            <div id={`${listId}-go`} className="t-caption px-3 py-1 font-semibold text-muted-ink">
              Go to
            </div>
            <ul className="m-0 list-none p-0" role="presentation">
              {goEntries.map(option)}
            </ul>
          </div>
        )}
        {(noteEntries.length > 0 || (q && search.status === 'error')) && (
          <div role="group" aria-labelledby={`${listId}-notes`}>
            <div id={`${listId}-notes`} className="t-caption px-3 py-1 font-semibold text-muted-ink">
              Notes
            </div>
            <ul className="m-0 list-none p-0" role="presentation">
              {noteEntries.map(option)}
            </ul>
          </div>
        )}
        {q && search.status === 'error' && (
          <p role="alert" className="t-body m-0 px-3 py-2 text-status-blocked">
            Could not search notes. {search.error.message}
          </p>
        )}
        {searching && search.status !== 'error' && (
          <p role="status" className="t-small m-0 px-3 py-2 text-muted-ink">
            Searching notes
          </p>
        )}
        {q && !searching && search.status === 'success' && entries.length === 0 && (
          <p className="t-body m-0 px-3 py-2 text-muted-ink">Nothing matches "{q}". Press Esc to close.</p>
        )}
      </div>
    </div>
  )
}

import { useEffect } from 'react'

/**
 * Stub for the command palette. It owns only the shortcut: Ctrl+K (Cmd+K on a
 * Mac) calls `onOpen` and stops the browser's own handling. Today the shell
 * passes a callback that focuses the search box; the Search package replaces
 * that callback with the palette itself, and nothing else changes.
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

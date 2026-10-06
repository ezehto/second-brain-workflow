import { useCallback, useSyncExternalStore } from 'react'

/** Matches while the viewport is at least `px` wide. Without `matchMedia` (a server, a bare test) it is `fallback`. */
export function useMinWidth(px: number, fallback = true): boolean {
  const query = `(min-width: ${px}px)`
  const subscribe = useCallback(
    (onChange: () => void) => {
      if (typeof window === 'undefined' || !window.matchMedia) return () => {}
      const list = window.matchMedia(query)
      list.addEventListener('change', onChange)
      return () => list.removeEventListener('change', onChange)
    },
    [query],
  )
  const snapshot = () => (typeof window === 'undefined' || !window.matchMedia ? fallback : window.matchMedia(query).matches)
  return useSyncExternalStore(subscribe, snapshot, () => fallback)
}

/** The width from which a list and a note reader sit side by side (assessment 5.6: 1024). */
export const SPLIT_MIN_WIDTH = 1024

/** True when the screen is wide enough for the split pane; below it a note opens as its own route. */
export const useSplitLayout = (): boolean => useMinWidth(SPLIT_MIN_WIDTH)

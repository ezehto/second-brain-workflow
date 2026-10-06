import { useCallback, useSyncExternalStore } from 'react'

/**
 * Which layout the shell uses, by width (assessment 5.6):
 * - `wide`    1280 and up: 224px rail with labels
 * - `compact` 832 to 1279: 72px icon rail with tooltips
 * - `tablet`  640 to 831: no rail, top bar with a menu, bottom tab bar
 * - `phone`   under 640: 48px top bar, bottom tab bar, New button in the top bar
 *
 * Chosen in JavaScript, not by hiding elements in CSS, so only one navigation
 * is in the document (no duplicate landmarks) and tests can pick a width.
 */
export type Viewport = 'wide' | 'compact' | 'tablet' | 'phone'

export const VIEWPORT_QUERIES = {
  wide: '(min-width: 1280px)',
  compact: '(min-width: 832px)',
  tablet: '(min-width: 640px)',
} as const

function snapshot(): Viewport {
  if (typeof window === 'undefined' || !window.matchMedia) return 'wide'
  if (window.matchMedia(VIEWPORT_QUERIES.wide).matches) return 'wide'
  if (window.matchMedia(VIEWPORT_QUERIES.compact).matches) return 'compact'
  if (window.matchMedia(VIEWPORT_QUERIES.tablet).matches) return 'tablet'
  return 'phone'
}

function subscribe(onChange: () => void) {
  if (typeof window === 'undefined' || !window.matchMedia) return () => {}
  const lists = Object.values(VIEWPORT_QUERIES).map((q) => window.matchMedia(q))
  lists.forEach((l) => l.addEventListener('change', onChange))
  return () => lists.forEach((l) => l.removeEventListener('change', onChange))
}

export function useViewport(): Viewport {
  return useSyncExternalStore(subscribe, snapshot, () => 'wide')
}

/** Phone and tablet widths use the bottom tab bar instead of a rail. */
export const hasTabBar = (v: Viewport) => v === 'phone' || v === 'tablet'

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

import { useSyncExternalStore } from 'react'

/**
 * Which layout the shell uses, by width (assessment 5.6):
 * - `wide`    1280 and up: 224px rail with labels
 * - `compact` 832 to 1279: 56px icon rail with tooltips
 * - `tablet`  640 to 831: no rail, top bar with a menu, bottom tab bar
 * - `phone`   under 640: 48px top bar, bottom tab bar, floating capture button
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

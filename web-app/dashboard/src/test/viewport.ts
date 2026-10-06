import { act } from '@testing-library/react'

type Listener = () => void
const registry = new Set<{ query: string; listeners: Set<Listener> }>()

function matches(query: string): boolean {
  const min = /\(min-width:\s*(\d+)px\)/.exec(query)
  const max = /\(max-width:\s*(\d+)px\)/.exec(query)
  const width = window.innerWidth
  return (!min || width >= Number(min[1])) && (!max || width <= Number(max[1]))
}

/** A matchMedia that evaluates width queries against `window.innerWidth`. */
export function installMatchMedia() {
  window.innerWidth = 1440
  window.matchMedia = ((query: string) => {
    const entry = { query, listeners: new Set<Listener>() }
    registry.add(entry)
    return {
      get matches() {
        return matches(query)
      },
      media: query,
      addEventListener: (_: string, l: Listener) => entry.listeners.add(l),
      removeEventListener: (_: string, l: Listener) => entry.listeners.delete(l),
    } as unknown as MediaQueryList
  }) as typeof window.matchMedia
}

/** Resize the window for a test and tell every media-query listener. */
export function setViewport(width: number) {
  act(() => {
    window.innerWidth = width
    registry.forEach((e) => e.listeners.forEach((l) => l()))
  })
}

export function resetViewport() {
  window.innerWidth = 1440
  registry.clear()
}

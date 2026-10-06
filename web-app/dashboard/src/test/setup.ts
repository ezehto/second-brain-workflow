import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach } from 'vitest'
import { installMatchMedia, resetViewport } from './viewport'

beforeEach(() => installMatchMedia())
afterEach(() => {
  cleanup()
  resetViewport()
  window.localStorage.clear()
})

// Radix Select and Dialog call browser APIs jsdom does not implement.
Element.prototype.hasPointerCapture ??= () => false
Element.prototype.setPointerCapture ??= () => {}
Element.prototype.releasePointerCapture ??= () => {}
Element.prototype.scrollIntoView ??= () => {}
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

export interface HeaderContext {
  /** The vault's today from the server (or the injected clock if it cannot answer). */
  today: string
  /** Wall-clock time of the last index pass, or null before the first. */
  lastPass: string | null
}

type Text = string | ((ctx: HeaderContext) => string)

/**
 * Each route's `handle`: what the top bar shows for that page. `title` is the
 * 20px h1 (on Today it is the date) and `subtitle` the line under it. `label`
 * is the short name for the browser tab; it defaults to the title.
 */
export interface PageHandle {
  title: Text
  subtitle: Text
  label?: string
}

export const resolveText = (text: Text, ctx: HeaderContext): string => (typeof text === 'function' ? text(ctx) : text)

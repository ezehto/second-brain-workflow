export interface HeaderContext {
  /** The vault's today from the injected clock. */
  today: string
  /** Wall-clock time of the last index pass, or null before the first. */
  lastPass: string | null
}

type Text = string | ((ctx: HeaderContext) => string)

/** Each route's `handle`: what the shell header shows for that page. */
export interface PageHandle {
  title: Text
  subtitle: Text
  /** The dashboard's date title is set larger than other pages' titles. */
  display?: boolean
}

export const resolveText = (text: Text, ctx: HeaderContext): string => (typeof text === 'function' ? text(ctx) : text)

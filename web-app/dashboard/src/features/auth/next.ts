import { routes } from '@/lib/routes'

/** The login URL for a page the person was sent away from; `next` is where they return after signing in. */
export function loginHref(from: { pathname: string; search: string }): string {
  const next = `${from.pathname}${from.search}`
  return next === routes.dashboard ? routes.login : `${routes.login}?next=${encodeURIComponent(next)}`
}

/**
 * Where to go after signing in. Only a path inside this app counts: anything else (another site,
 * a protocol-relative `//host`, the login page itself) is the dashboard, so `?next=` cannot be
 * used to send a person elsewhere.
 */
export function safeNext(next: string | null): string {
  if (!next || !next.startsWith('/') || next.startsWith('//')) return routes.dashboard
  // Browsers drop tabs and newlines and read a backslash as a slash, so `/\t/host` can mean `//host`.
  if ([...next].some((c) => c.charCodeAt(0) <= 0x1f || c === '\\')) return routes.dashboard
  const origin = 'http://app.invalid'
  let resolved: URL
  try {
    resolved = new URL(next, origin)
  } catch {
    return routes.dashboard
  }
  if (resolved.origin !== origin || resolved.pathname === routes.login) return routes.dashboard
  return next
}

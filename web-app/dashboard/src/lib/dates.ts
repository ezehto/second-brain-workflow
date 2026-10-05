import type { IsoDate } from './clock'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** The shown text for a value the data may not have. */
export const NOT_AVAILABLE = 'N/A'

export function isIsoDate(value: unknown): value is IsoDate {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
}

/** `2026-10-06` to `Oct 6`; a missing or unreadable date is `N/A`. */
export function formatShortDate(date: string | null | undefined): string {
  if (!date || !isIsoDate(date.slice(0, 10))) return NOT_AVAILABLE
  return `${MONTHS[parseInt(date.slice(5, 7), 10) - 1]} ${parseInt(date.slice(8, 10), 10)}`
}

/** `2026-10-06` to `Tuesday 6 October`. */
export function formatDayTitle(date: IsoDate): string {
  const parsed = new Date(`${date}T00:00:00Z`)
  if (Number.isNaN(parsed.getTime())) return NOT_AVAILABLE
  const weekday = new Intl.DateTimeFormat('en-GB', { weekday: 'long', timeZone: 'UTC' }).format(parsed)
  const month = new Intl.DateTimeFormat('en-GB', { month: 'long', timeZone: 'UTC' }).format(parsed)
  return `${weekday} ${parseInt(date.slice(8, 10), 10)} ${month}`
}

/** Whole days from `from` to `to` (both `YYYY-MM-DD`). */
export function daysBetween(from: IsoDate, to: IsoDate): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000)
}

/**
 * The API sends `modified` as local ISO time with the vault offset
 * (`2026-10-06T11:20:00+08:00`), so the wall-clock parts are read from the
 * string and never converted through the browser's zone.
 */
export function wallDate(iso: string): IsoDate {
  return iso.slice(0, 10)
}
export function wallTime(iso: string): string {
  return iso.slice(11, 16)
}

/** Today's changes show the time; older ones show the date. */
export function formatWhen(modified: string, today: IsoDate): string {
  return wallDate(modified) === today ? wallTime(modified) : formatShortDate(modified)
}

export function formatTimeOfDay(iso: string | null | undefined): string {
  return iso ? wallTime(iso) : NOT_AVAILABLE
}

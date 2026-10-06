import { NOT_AVAILABLE, wallDate, wallTime } from '@/lib/dates'

/** `2026-10-06T14:39:52+08:00` to `2026-10-06 14:39`; before the first pass, `N/A`. */
export function formatPass(iso: string | null): string {
  return iso ? `${wallDate(iso)} ${wallTime(iso)}` : NOT_AVAILABLE
}

/** 700 to `0.7 s`; a missing duration is `N/A`. */
export function formatDuration(ms: number | null): string {
  return ms === null ? NOT_AVAILABLE : `${(ms / 1000).toFixed(1)} s`
}

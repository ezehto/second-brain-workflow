import { NOT_AVAILABLE } from '@/lib/dates'

/** A thin progress track. Pass the counts as text beside it; this is only the bar. */
export function ProgressBar({ percent, label }: { percent: number | null; label: string }) {
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent ?? undefined}
      aria-valuetext={percent === null ? NOT_AVAILABLE : `${percent}%`}
      className="h-2 flex-1 overflow-hidden rounded-full bg-inset"
    >
      <div className="h-2 rounded-full bg-brand" style={{ width: `${percent ?? 0}%` }} />
    </div>
  )
}

export interface DonutSegment {
  label: string
  count: number
  color: string
}

const SIZE = 140
const STROKE = 20
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
/** Surface-coloured gap between neighbouring segments, in px of arc. */
const GAP = 2

/**
 * Parts of a whole: a ring with the total in the centre and a legend of
 * colour dot, word and count. The legend carries identity, so colour is never
 * the only signal. Zero-count segments are not drawn.
 */
export function Donut({
  segments,
  total,
  centerLabel,
  ariaLabel,
}: {
  segments: DonutSegment[]
  total: number
  centerLabel: string
  ariaLabel: string
}) {
  const drawn = segments.filter((s) => s.count > 0)
  const sum = drawn.reduce((n, s) => n + s.count, 0)
  const arcs = drawn.map((s, i) => {
    const before = drawn.slice(0, i).reduce((n, x) => n + x.count, 0)
    return { ...s, length: (s.count / sum) * CIRCUMFERENCE, offset: (before / sum) * CIRCUMFERENCE }
  })
  return (
    <div className="flex flex-wrap items-center gap-5 px-5 pt-1 pb-5">
      <div className="relative size-[140px] flex-none" role="img" aria-label={ariaLabel}>
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="size-full -rotate-90" aria-hidden="true">
          <circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} fill="none" stroke="var(--color-inset)" strokeWidth={STROKE} />
          {arcs.map((s) => {
            const dash = arcs.length > 1 ? Math.max(s.length - GAP, 0.5) : s.length
            return (
              <circle
                key={s.label}
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={RADIUS}
                fill="none"
                stroke={s.color}
                strokeWidth={STROKE}
                strokeDasharray={`${dash} ${CIRCUMFERENCE - dash}`}
                strokeDashoffset={-s.offset}
              >
                <title>{`${s.label}: ${s.count}`}</title>
              </circle>
            )
          })}
        </svg>
        <div className="absolute inset-5 flex flex-col items-center justify-center">
          <span className="num text-[26px] leading-none font-extrabold">{total}</span>
          <span className="note">{centerLabel}</span>
        </div>
      </div>
      <ul className="m-0 flex min-w-[140px] flex-1 list-none flex-col gap-1.5 p-0">
        {segments.map((s) => (
          <li key={s.label} className="flex items-center gap-2 text-[13px]">
            <span aria-hidden="true" className="size-[9px] flex-none rounded-full" style={{ background: s.color }} />
            <span className="flex-1">{s.label}</span>
            <span className="num font-bold">{s.count}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

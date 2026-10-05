import { Link } from 'react-router'
import { cn } from '@/lib/utils'
import { TONE_TINT, type StatusTone } from '@/domain/status'
import { Icon, type IconName } from './Icon'

export type TileTone = StatusTone | 'brand'
const BRAND_TINT = 'bg-brand-soft text-brand'

/** A count with an icon chip and a label. Links to the list it counts. */
export function StatTile({
  icon,
  tone,
  value,
  label,
  to,
}: {
  icon: IconName
  tone: TileTone
  value: number | string
  label: string
  to: string
}) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3.5 rounded-card border border-line bg-surface px-[18px] py-4 text-left text-ink no-underline hover:border-brand-fill hover:text-ink"
    >
      <span
        className={cn(
          'inline-flex size-[42px] flex-none items-center justify-center rounded-tile',
          tone === 'brand' ? BRAND_TINT : TONE_TINT[tone],
        )}
      >
        <Icon name={icon} className="size-5" />
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="num text-[26px] leading-[1.1] font-extrabold">{value}</span>
        <span className="text-[13px] text-muted-ink">{label}</span>
      </span>
    </Link>
  )
}

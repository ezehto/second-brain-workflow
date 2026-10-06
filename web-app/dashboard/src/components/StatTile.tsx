import { Link } from 'react-router'
import { cn } from '@/lib/utils'
import { TONE_TINT, type StatusTone } from '@/domain/status'
import { Icon, type IconName } from './Icon'

export type TileTone = StatusTone | 'brand'
const BRAND_TINT = 'bg-brand-soft text-brand'

/**
 * A count with an icon chip and a label. Links to the list it counts.
 * `compact` is the dense variant for the rebuilt Dashboard: 64px high, a 32px
 * chip, the figure and the label each on one line.
 * `condensed` (with `compact`) is for a row of six that must fit under 1280px:
 * there the chip is dropped and the label may wrap to two lines.
 */
export function StatTile({
  icon,
  tone,
  value,
  label,
  to,
  compact = false,
  condensed = false,
}: {
  icon: IconName
  tone: TileTone
  value: number | string
  label: string
  to: string
  compact?: boolean
  condensed?: boolean
}) {
  return (
    <Link
      to={to}
      className={cn(
        'flex items-center border border-line bg-surface text-left text-ink no-underline hover:border-brand-fill hover:text-ink',
        compact ? cn('gap-3 rounded-card px-3', condensed ? 'min-h-16 py-1' : 'h-16') : 'gap-3.5 rounded-card px-[18px] py-4',
      )}
    >
      <span
        className={cn(
          'inline-flex flex-none items-center justify-center',
          compact ? 'size-8 rounded-lg' : 'size-[42px] rounded-tile',
          condensed && 'max-fullrail:hidden',
          tone === 'brand' ? BRAND_TINT : TONE_TINT[tone],
        )}
      >
        <Icon name={icon} className={compact ? 'size-[18px]' : 'size-5'} />
      </span>
      <span className="flex min-w-0 flex-col">
        <span className={cn('num font-bold', compact ? 't-page' : 'text-[26px] leading-[1.1]')}>{value}</span>
        <span className={cn('text-muted-ink', condensed ? 'max-fullrail:line-clamp-2 fullrail:truncate' : 'truncate', compact ? 't-small' : 'text-[13px]')}>{label}</span>
      </span>
    </Link>
  )
}

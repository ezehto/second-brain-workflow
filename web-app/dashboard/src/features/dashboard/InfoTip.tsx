import { Icon } from '@/components/Icon'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

/**
 * A small "i" button that explains a stated rule. The rule is in a tooltip on
 * hover and keyboard focus and in the accessible name, so it is not lost to
 * touch or screen readers.
 */
export function InfoTip({ label, rule }: { label: string; rule: string }) {
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="inline-flex size-6 cursor-help items-center justify-center rounded-full text-muted-ink hover:text-ink max-rail:size-11"
          >
            <Icon name="info" className="size-4" />
            <span className="sr-only">
              {label}: {rule}
            </span>
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-80">{rule}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

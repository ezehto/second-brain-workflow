import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

/**
 * One labelled badge for data that is sample or arrives in a later phase,
 * instead of a source caption repeated on every section. The detail (where the
 * data would come from) is in the tooltip, reachable by keyboard, and in the
 * accessible name.
 */
export function PreviewBadge({ detail, label = 'Preview' }: { detail: string; label?: string }) {
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            tabIndex={0}
            className="t-caption inline-flex h-5 cursor-help items-center rounded-full border border-line px-2 font-medium text-muted-ink"
          >
            {label}
            <span className="sr-only">: {detail}</span>
          </span>
        </TooltipTrigger>
        <TooltipContent>{detail}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

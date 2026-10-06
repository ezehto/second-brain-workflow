import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

/**
 * One labelled badge for data that is sample or arrives in a later phase,
 * instead of a source caption repeated on every section. The detail (where the
 * data would come from) shows in a tooltip on hover and keyboard focus, in a
 * popover on tap or click (touch has no hover), and is in the accessible name.
 */
export function PreviewBadge({ detail, label = 'Preview' }: { detail: string; label?: string }) {
  return (
    <TooltipProvider delayDuration={150}>
      <Popover>
        <Tooltip>
          <TooltipTrigger asChild>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="t-caption inline-flex h-5 cursor-pointer items-center rounded-full border border-line bg-transparent px-2 font-medium text-muted-ink relative max-rail:after:absolute max-rail:after:-inset-3 max-rail:after:content-['']"
              >
                {label}
                <span className="sr-only">: {detail}</span>
              </button>
            </PopoverTrigger>
          </TooltipTrigger>
          <TooltipContent>{detail}</TooltipContent>
        </Tooltip>
        <PopoverContent>{detail}</PopoverContent>
      </Popover>
    </TooltipProvider>
  )
}

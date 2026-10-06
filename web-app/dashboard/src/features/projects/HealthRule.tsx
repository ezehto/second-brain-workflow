import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { HEALTH_RULE } from '@/domain/health'

/** The stated health rule: a tooltip on hover and focus, a popover on tap. */
export function HealthRule() {
  return (
    <TooltipProvider delayDuration={150}>
      <Popover>
        <Tooltip>
          <TooltipTrigger asChild>
            <PopoverTrigger asChild>
              <button type="button" className="linkbtn t-small relative cursor-pointer max-rail:after:absolute max-rail:after:-inset-3 max-rail:after:content-['']">
                How health is decided
                <span className="sr-only">: {HEALTH_RULE}</span>
              </button>
            </PopoverTrigger>
          </TooltipTrigger>
          <TooltipContent>{HEALTH_RULE}</TooltipContent>
        </Tooltip>
        <PopoverContent>{HEALTH_RULE}</PopoverContent>
      </Popover>
    </TooltipProvider>
  )
}

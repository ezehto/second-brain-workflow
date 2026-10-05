import { Button } from '@/components/ui/button'

/** A section failed to load: what happened, and a retry. */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-2.5 px-5 pb-5">
      <p className="m-0 font-medium text-status-blocked">Could not load this section. {message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

import { Link } from 'react-router'
import { Card, CardHead, InsetItem } from '@/components/Card'
import { Icon } from '@/components/Icon'
import { Button } from '@/components/ui/button'
import { routes } from '@/lib/routes'
import { previewImproving } from '@/preview'

/** Preview: learning needs the upskilling notes (Phase 3), Claude usage needs session logs (Phase 5). */
export function Improving() {
  return (
    <Card>
      <CardHead title="How you are improving">
        <Button asChild variant="secondary" size="sm">
          <Link to={routes.upskilling}>Open upskilling</Link>
        </Button>
      </CardHead>
      <div className="flex flex-col gap-3 px-5 pb-5">
        {previewImproving.map((item) => (
          <InsetItem key={item.label} className="flex gap-3">
            <span className="inline-flex size-[30px] flex-none items-center justify-center rounded-[9px] bg-brand-soft text-brand">
              <Icon name={item.icon} className="size-5" />
            </span>
            <div className="flex min-w-0 flex-col">
              <span className="font-semibold">{item.label}</span>
              <span>
                {item.emphasis && <strong>{item.emphasis} </strong>}
                {item.text}
              </span>
              <span className="note">{item.source}</span>
            </div>
          </InsetItem>
        ))}
      </div>
    </Card>
  )
}

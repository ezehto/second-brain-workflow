import { Link } from 'react-router'
import { Card, CardHead, CardRow } from '@/components/Card'
import { PreviewBadge } from '@/components/PreviewBadge'
import { Button } from '@/components/ui/button'
import { routes } from '@/lib/routes'
import { previewImproving } from '@/preview'

/** Preview: one row. Needs the upskilling notes (Phase 3). */
export function Learning() {
  const learning = previewImproving.find((i) => i.label === 'Learning')
  if (!learning) return null
  return (
    <Card aria-label="Learning">
      <CardHead title="Learning">
        <PreviewBadge detail={learning.source} />
        <Button asChild variant="secondary" size="sm">
          <Link to={routes.upskilling}>Open upskilling</Link>
        </Button>
      </CardHead>
      <CardRow lines={2} className="grid-cols-1 py-1.5">
        <span className="t-body">{learning.text}</span>
      </CardRow>
    </Card>
  )
}

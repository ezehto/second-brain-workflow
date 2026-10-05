import { Link } from 'react-router'
import { Card } from '@/components/Card'
import { routes } from '@/lib/routes'

/** Every rail destination that has no page yet lands here, inside the shell. */
export function NotBuiltPage() {
  return (
    <Card className="max-w-xl p-6">
      <h2 className="text-base">Not built yet</h2>
      <p className="mt-2 mb-4 text-muted-ink">
        This page comes after the Dashboard has been reviewed. The navigation, search and quick actions around it already work.
      </p>
      <Link to={routes.dashboard}>Back to the dashboard</Link>
    </Card>
  )
}

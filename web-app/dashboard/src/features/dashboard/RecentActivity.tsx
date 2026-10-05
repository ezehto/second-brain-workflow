import { Link } from 'react-router'
import type { Query } from '@/api/useQuery'
import type { DashboardResponse } from '@/api/types'
import { ActivityList } from '@/components/ActivityList'
import { Card, CardHead } from '@/components/Card'
import { QueryBoundary } from '@/components/QueryBoundary'
import { Button } from '@/components/ui/button'
import { useToday } from '@/lib/clock'
import { formatWhen } from '@/lib/dates'
import { noteHref, routes } from '@/lib/routes'

/** Latest changed notes. Real Phase 1 data: the vault is the only source until Phase 4. */
export function RecentActivity({ query }: { query: Query<DashboardResponse> }) {
  const today = useToday()
  return (
    <Card>
      <CardHead title="Recent activity" note="Vault only until Phase 4">
        <Button asChild variant="secondary" size="sm">
          <Link to={routes.timeline}>Open timeline</Link>
        </Button>
      </CardHead>
      <QueryBoundary query={query} isEmpty={(d) => d.recent_activity.length === 0} empty="Nothing has changed in the vault yet.">
        {(d) => (
          <ActivityList
            items={d.recent_activity.map((n) => ({
              key: n.path,
              when: formatWhen(n.modified, today),
              meta: `${n.type}, vault`,
              title: n.title,
              href: noteHref(n.path),
            }))}
          />
        )}
      </QueryBoundary>
    </Card>
  )
}

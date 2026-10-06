import { Link } from 'react-router'
import type { Query } from '@/api/useQuery'
import type { NoteSummary } from '@/api/types'
import { Card, CardHead, CardRow } from '@/components/Card'
import { QueryBoundary } from '@/components/QueryBoundary'
import { daysSinceCreated, proposedDecisions } from '@/domain/dashboard'
import type { ProjectLookup } from '@/domain/projects'
import { useToday } from '@/lib/clock'
import { NOT_AVAILABLE } from '@/lib/dates'
import { plural } from '@/lib/plural'
import { noteHref } from '@/lib/routes'

/** Decisions still proposed, oldest first, each opening the note reader. */
export function DecisionsToMake({ decisions, projects }: { decisions: Query<NoteSummary[]>; projects: ProjectLookup }) {
  const today = useToday()
  const open = decisions.status === 'success' ? proposedDecisions(decisions.data) : []
  return (
    <Card aria-label="Decisions to make">
      <CardHead title="Decisions to make" count={decisions.status === 'success' ? open.length : undefined} />
      <QueryBoundary query={decisions} rows={2} isEmpty={() => open.length === 0} empty="No decision is waiting.">
        {() =>
          open.map((d) => {
            const age = daysSinceCreated(d, today)
            return (
              <CardRow key={d.path} lines={2} className="grid-cols-1 py-1.5">
                <div className="flex min-w-0 flex-col">
                  <Link to={noteHref(d.path)} className="linkbtn t-body truncate">
                    {d.title}
                  </Link>
                  <span className="t-small truncate text-muted-ink">
                    {projects.title(d.project)} · proposed {age === null ? NOT_AVAILABLE : age === 0 ? 'today' : `${plural(age, 'day')} ago`}
                  </span>
                </div>
              </CardRow>
            )
          })
        }
      </QueryBoundary>
    </Card>
  )
}

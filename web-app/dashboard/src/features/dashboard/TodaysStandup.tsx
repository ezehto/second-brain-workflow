import { Link } from 'react-router'
import type { Query } from '@/api/useQuery'
import type { DashboardResponse } from '@/api/types'
import { Card, CardHead } from '@/components/Card'
import { QueryBoundary } from '@/components/QueryBoundary'
import { StatusChip } from '@/components/StatusChip'
import { Button } from '@/components/ui/button'
import { summarizeStandup, type StandupSummary } from '@/domain/standup'
import type { StatusTone } from '@/domain/status'
import { useToday } from '@/lib/clock'
import { plural } from '@/lib/plural'
import { routes } from '@/lib/routes'

export function standupLabel(s: StandupSummary): { label: string; tone: StatusTone; summary: string } {
  if (!s.exists) {
    return {
      label: 'Not started',
      tone: 'neutral',
      summary: `Not started. ${plural(s.today_count, 'task')} and ${plural(s.blocker_count, 'blocker')} would be carried forward.`,
    }
  }
  if (s.untouched) {
    return { label: 'Untouched', tone: 'neutral', summary: 'Created by Obsidian, still empty. It can be filled with carry-forward.' }
  }
  return { label: 'Edited by hand', tone: 'progress', summary: 'Edited by hand. Shown as written.' }
}

/** Where today's daily note stands: missing, untouched, or edited. */
export function TodaysStandup({ query }: { query: Query<DashboardResponse> }) {
  const today = useToday()
  return (
    <Card>
      <CardHead title="Today's standup">
        <Button asChild variant="secondary" size="sm">
          <Link to={routes.standups}>Open standup</Link>
        </Button>
      </CardHead>
      <QueryBoundary query={query} rows={2}>
        {(d) => {
          const standup = summarizeStandup(d.standup, today)
          const state = standupLabel(standup)
          return (
            <div className="flex flex-col gap-2.5 px-5 pb-[18px]">
              <div className="flex flex-wrap items-center gap-2">
                <span className="mono">{standup.path}</span>
                <StatusChip label={state.label} tone={state.tone} />
              </div>
              <div className="text-muted-ink">{state.summary}</div>
            </div>
          )
        }}
      </QueryBoundary>
    </Card>
  )
}

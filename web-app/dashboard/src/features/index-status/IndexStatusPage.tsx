import { useCallback, useState } from 'react'
import { useApi, useInvalidate } from '@/api/ApiProvider'
import type { IndexStatus } from '@/api/types'
import { useQuery } from '@/api/useQuery'
import { Card, CardFootnote } from '@/components/Card'
import { QueryBoundary } from '@/components/QueryBoundary'
import { Button } from '@/components/ui/button'
import { indexProblemCount } from '@/domain/indexStatus'
import { plural } from '@/lib/plural'
import { formatDuration, formatPass } from './format'
import { Integrations } from './Integrations'
import { Problems } from './Problems'
import { TypeBars } from './TypeBars'

type Refresh = { state: 'idle' } | { state: 'running' } | { state: 'done'; pass: IndexStatus } | { state: 'failed'; message: string }

const noteTotal = (s: IndexStatus) => Object.values(s.counts_by_type).reduce((a, b) => a + b, 0)

function Figure({ label, value, alert }: { label: string; value: string | number; alert?: boolean }) {
  return (
    <div className="flex flex-col">
      <span className="t-small text-muted-ink">{label}</span>
      <span className={alert ? 'num font-semibold text-status-blocked' : 'num font-semibold'}>{value}</span>
    </div>
  )
}

/** Can I trust what I am seeing: the last pass, counts by type, and every problem with its note. */
export function IndexStatusPage() {
  const client = useApi()
  const invalidate = useInvalidate()
  const status = useQuery(useCallback(() => client.getIndexStatus(), [client]))
  const [refresh, setRefresh] = useState<Refresh>({ state: 'idle' })
  const running = refresh.state === 'running'

  const run = () => {
    if (running) return
    setRefresh({ state: 'running' })
    client.refreshIndex().then(
      (pass) => {
        setRefresh({ state: 'done', pass })
        invalidate()
      },
      (error: unknown) => setRefresh({ state: 'failed', message: error instanceof Error ? error.message : String(error) }),
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 px-3 py-3">
          {status.status === 'success' && (
            <>
              <Figure label="Last pass" value={formatPass(status.data.last_pass_at)} />
              <Figure label="Duration" value={formatDuration(status.data.duration_ms)} />
              <Figure label="Notes indexed" value={noteTotal(status.data)} />
              <Figure label="Problems" value={indexProblemCount(status.data)} alert={indexProblemCount(status.data) > 0} />
            </>
          )}
          <div className="ml-auto">
            <Button onClick={run} disabled={running}>
              {running ? 'Refreshing' : 'Refresh index'}
            </Button>
          </div>
        </div>
        {status.status === 'success' && status.data.test_mode && (
          <CardFootnote>Test mode: today is pinned to {status.data.test_mode.today}.</CardFootnote>
        )}
        {refresh.state === 'done' && (
          <p role="status" className="m-0 border-t border-line px-3 py-2 font-medium text-status-done">
            Pass finished in {formatDuration(refresh.pass.duration_ms)}: {plural(noteTotal(refresh.pass), 'note')} indexed,{' '}
            {plural(indexProblemCount(refresh.pass), 'problem')}.
          </p>
        )}
        {refresh.state === 'failed' && (
          <p role="alert" className="m-0 border-t border-line px-3 py-2 font-medium text-status-blocked">
            Could not refresh the index. {refresh.message}
          </p>
        )}
      </Card>

      <QueryBoundary query={status} rows={5}>
        {(data) => (
          <div className="grid grid-cols-[repeat(auto-fit,minmax(min(400px,100%),1fr))] items-start gap-4">
            <TypeBars counts={data.counts_by_type} />
            <Problems status={data} />
          </div>
        )}
      </QueryBoundary>

      <Integrations />
    </div>
  )
}

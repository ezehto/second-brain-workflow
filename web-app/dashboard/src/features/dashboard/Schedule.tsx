import { Card, CardHead, CardRow } from '@/components/Card'
import { PreviewBadge } from '@/components/PreviewBadge'
import { previewMeetings } from '@/preview'

/** Preview: needs Calendar (Phase 4). */
export function Schedule() {
  return (
    <Card aria-label="Schedule">
      <CardHead title="Schedule" count={previewMeetings.items.length}>
        <PreviewBadge detail={previewMeetings.source} />
      </CardHead>
      <ul className="m-0 list-none p-0">
        {previewMeetings.items.map((m) => (
          <li key={m.time}>
            <CardRow className="grid-cols-[3.5rem_minmax(0,1fr)_auto]">
              <span className="mono num text-muted-ink">{m.time}</span>
              <span className="t-body min-w-0 truncate">{m.title}</span>
              <span className="t-small text-muted-ink">{m.length}</span>
            </CardRow>
          </li>
        ))}
      </ul>
    </Card>
  )
}

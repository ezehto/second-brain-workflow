import { Card, CardHead, CardRow } from '@/components/Card'
import { previewMeetings } from '@/preview'

/** Preview: needs Calendar (Phase 4). Rendered from `src/preview`, labelled as sample data. */
export function TodaysMeetings() {
  return (
    <Card>
      <CardHead title="Today's meetings" note={previewMeetings.source} />
      <ul className="m-0 list-none p-0">
        {previewMeetings.items.map((m) => (
          <li key={m.time}>
            <CardRow className="grid-cols-[56px_minmax(0,1fr)_auto]">
              <span className="mono num rounded-lg bg-brand-soft px-2 py-0.5 text-center text-brand-hover">{m.time}</span>
              <span>{m.title}</span>
              <span className="text-[13px] text-muted-ink">{m.length}</span>
            </CardRow>
          </li>
        ))}
      </ul>
    </Card>
  )
}

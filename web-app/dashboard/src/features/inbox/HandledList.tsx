import { Card, CardHead, CardRow } from '@/components/Card'
import { StatusChip } from '@/components/StatusChip'

export interface Handled {
  path: string
  text: string
  outcome: 'converted' | 'dismissed'
  /** The file the action wrote: the new note for a conversion, the capture for a dismissal. */
  written: string
}

/** What this visit converted or dismissed, with the file each action wrote. Lost on reload by design: the vault is the record. */
export function HandledList({ items }: { items: Handled[] }) {
  if (items.length === 0) return null
  return (
    <Card>
      <CardHead title="Handled this session" count={items.length} />
      <ul className="m-0 list-none p-0">
        {items.map((item) => (
          <CardRow key={`${item.path}-${item.outcome}`} lines={2} className="grid-cols-[minmax(0,1fr)_auto]" {...{ role: 'listitem' }}>
            <div className="flex min-w-0 flex-col">
              <span className="t-body truncate">{item.text}</span>
              <span className="t-small truncate text-muted-ink">
                {item.outcome === 'converted' ? 'Wrote' : 'Set status: dismissed in'} {item.written}
              </span>
            </div>
            <StatusChip status={item.outcome === 'converted' ? 'triaged' : 'dismissed'} label={item.outcome} />
          </CardRow>
        ))}
      </ul>
    </Card>
  )
}

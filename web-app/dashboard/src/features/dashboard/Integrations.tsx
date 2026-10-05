import { Card, CardHead, CardRow } from '@/components/Card'
import { Icon } from '@/components/Icon'
import { StatusChip } from '@/components/StatusChip'
import { previewIntegrations } from '@/preview'

/** Preview: integrations arrive in Phase 4. This only shows where the data would come from. */
export function Integrations() {
  return (
    <Card>
      <CardHead title="Integrations" note={previewIntegrations.source} />
      <ul className="m-0 list-none p-0">
        {previewIntegrations.items.map((i) => (
          <li key={i.name}>
            <CardRow className="grid-cols-[30px_minmax(0,1fr)_auto]">
              <span className="inline-flex size-[30px] items-center justify-center rounded-[9px] bg-brand-soft text-brand">
                <Icon name={i.icon} className="size-5" />
              </span>
              <div className="flex flex-col">
                <span className="font-semibold">{i.name}</span>
                <span className="note">{i.purpose}</span>
              </div>
              <StatusChip label={i.state} tone="neutral" />
            </CardRow>
          </li>
        ))}
      </ul>
    </Card>
  )
}

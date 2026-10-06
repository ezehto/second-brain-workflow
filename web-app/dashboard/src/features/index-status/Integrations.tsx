import { Card, CardHead, CardRow } from '@/components/Card'
import { PreviewBadge } from '@/components/PreviewBadge'

const INTEGRATIONS = ['Jira', 'GitLab', 'Calendar']

/** Compact stub: integrations arrive in Phase 4. */
export function Integrations() {
  return (
    <Card>
      <CardHead title="Integrations">
        <PreviewBadge detail="Jira, GitLab and Calendar connect in Phase 4. Nothing is read from them yet." />
      </CardHead>
      <ul className="m-0 list-none p-0">
        {INTEGRATIONS.map((name) => (
          <li key={name}>
            <CardRow className="min-h-8 grid-cols-[minmax(0,1fr)_auto]">
              <span className="font-medium">{name}</span>
              <span className="text-muted-ink">Not connected</span>
            </CardRow>
          </li>
        ))}
      </ul>
    </Card>
  )
}

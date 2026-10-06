import { Card, CardHead, CardRow } from '@/components/Card'

/** Notes by type as horizontal bars, widest first, each with its number as text. */
export function TypeBars({ counts }: { counts: Record<string, number> }) {
  const rows = Object.entries(counts).sort(([a, x], [b, y]) => y - x || a.localeCompare(b))
  const max = Math.max(1, ...rows.map(([, n]) => n))
  return (
    <Card>
      <CardHead title="Notes by type" />
      {rows.length === 0 ? (
        <CardRow className="text-muted-ink">No notes indexed yet. Refresh the index after adding notes to the vault.</CardRow>
      ) : (
        <ul className="m-0 list-none p-0">
          {rows.map(([type, n]) => (
            <li key={type}>
              <CardRow className="min-h-8 grid-cols-[96px_minmax(0,1fr)_40px]">
                <span className="t-small font-mono">{type}</span>
                <div aria-hidden="true" className="h-2 overflow-hidden rounded-full bg-inset">
                  <div className="h-2 rounded-full bg-muted-ink" style={{ width: `${Math.round((n / max) * 100)}%` }} />
                </div>
                <span className="num text-right font-medium">{n}</span>
              </CardRow>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

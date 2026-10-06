import { useState, type ReactNode } from 'react'
import { Card, CardHead, CardRow } from '@/components/Card'
import { PreviewBadge } from '@/components/PreviewBadge'
import { StatusChip } from '@/components/StatusChip'
import { formatShortDate } from '@/lib/dates'
import { cn } from '@/lib/utils'
import { EMPTY_PREVIEW_PROJECT, previewProjectData, previewTimeline, type PreviewArchNode } from '@/preview'

export const LATER_TABS = [
  { value: 'timeline', label: 'Timeline' },
  { value: 'architecture', label: 'Architecture' },
  { value: 'incidents', label: 'Incidents' },
  { value: 'deployments', label: 'Deployments' },
  { value: 'learning', label: 'Learning' },
] as const
export type LaterTab = (typeof LATER_TABS)[number]['value']

const dataFor = (slug: string) => previewProjectData.bySlug[slug] ?? EMPTY_PREVIEW_PROJECT

/** A Later tab: one card, one preview badge that says where the data would come from. */
function LaterCard({ title, detail, count, children }: { title: string; detail: string; count?: number; children: ReactNode }) {
  return (
    <Card>
      <CardHead title={title} count={count}>
        <PreviewBadge detail={detail} />
      </CardHead>
      {children}
    </Card>
  )
}

const Empty = ({ children }: { children: string }) => <p className="m-0 border-t border-line px-3 py-3 text-muted-ink">{children}</p>

function TimelineTab({ slug }: { slug: string }) {
  const events = previewTimeline.events.filter((e) => e.projects.includes(slug))
  const tickets = dataFor(slug).tickets
  return (
    <div className="flex flex-col gap-4">
      <LaterCard title="What happened in this project?" detail={previewTimeline.source} count={events.length}>
        {events.length === 0 ? (
          <Empty>No sample events for this project.</Empty>
        ) : (
          <ul className="m-0 list-none p-0">
            {events.map((e) => (
              <li key={e.id}>
                <CardRow className="grid-cols-[6.5rem_minmax(0,1fr)_auto]">
                  <span className="num t-small text-muted-ink">
                    {formatShortDate(e.date)} {e.time}
                  </span>
                  <span className="t-body truncate">
                    <span className="text-muted-ink">{previewTimeline.eventTypes[e.type] ?? e.type}: </span>
                    {e.title}
                  </span>
                  <span className="t-caption text-muted-ink">{previewTimeline.sourceLabels[e.source]}</span>
                </CardRow>
              </li>
            ))}
          </ul>
        )}
      </LaterCard>
      {tickets.length > 0 && (
        <Card>
          <CardHead title="Which tickets are open?" count={tickets.length} />
          <ul className="m-0 list-none p-0">
            {tickets.map((t) => (
              <li key={t.key}>
                <CardRow lines={2} className="grid-cols-[minmax(0,1fr)_auto]">
                  <div className="flex min-w-0 flex-col">
                    <span className="t-body truncate">
                      {t.key} {t.title}
                    </span>
                    <span className="t-small truncate text-muted-ink">Linked to {t.task}</span>
                  </div>
                  <StatusChip label={t.status} tone={t.tone} />
                </CardRow>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}

const CELL_W = 100
const CELL_H = 100
const COLS = 4
const ROWS = 2

function NodeDetail({ node }: { node: PreviewArchNode }) {
  const section = (title: string, items: string[]) => (
    <div className="flex flex-col">
      <h4 className="t-small font-semibold text-muted-ink">{title}</h4>
      {items.length === 0 ? <span className="t-body">None recorded</span> : items.map((i) => <span key={i} className="t-body">{i}</span>)}
    </div>
  )
  return (
    <div aria-live="polite" className="flex min-w-0 flex-col gap-3 rounded-tile bg-inset p-3">
      <div className="flex flex-col">
        <h3 className="t-panel font-semibold">{node.name}</h3>
        <span className="t-small text-muted-ink">{node.kind}. Select another box to switch.</span>
      </div>
      {section('Purpose', [node.purpose])}
      {section('Related decisions', node.decisions)}
      {section('Related tasks', node.tasks)}
      {section('Open risks', node.risks)}
    </div>
  )
}

/** How does the work flow through the system? A static map; selecting a box shows its detail. */
function ArchitectureTab({ slug }: { slug: string }) {
  const { nodes, edges } = dataFor(slug).architecture
  const [picked, setPicked] = useState<string | null>(null)
  const node = nodes.find((n) => n.id === picked) ?? nodes.find((n) => n.id === 'handler') ?? nodes[0]
  const center = (id: string) => {
    const n = nodes.find((x) => x.id === id)
    return n ? { x: (n.col + 0.5) * CELL_W, y: (n.row + 0.5) * CELL_H } : null
  }
  return (
    <LaterCard title="How does a payment callback flow through the system?" detail={previewProjectData.source}>
      {!node ? (
        <Empty>No architecture sample for this project.</Empty>
      ) : (
        <div className="grid grid-cols-1 items-start gap-4 border-t border-line p-3 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <div className="overflow-x-auto">
            <div className="relative h-56 min-w-[640px]">
              <svg aria-hidden="true" viewBox={`0 0 ${COLS * CELL_W} ${ROWS * CELL_H}`} preserveAspectRatio="none" className="absolute inset-0 size-full text-muted-ink">
                {edges.map((e) => {
                  const a = center(e.from)
                  const b = center(e.to)
                  return a && b ? <line key={`${e.from}-${e.to}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="currentColor" strokeWidth={1.5} vectorEffect="non-scaling-stroke" /> : null
                })}
              </svg>
              {edges.map((e) => {
                const a = center(e.from)
                const b = center(e.to)
                if (!a || !b) return null
                return (
                  <span
                    key={`${e.from}-${e.to}`}
                    className="t-caption absolute -translate-x-1/2 -translate-y-1/2 bg-surface px-1 text-muted-ink"
                    style={{ left: `${(((a.x + b.x) / 2) / (COLS * CELL_W)) * 100}%`, top: `${(((a.y + b.y) / 2) / (ROWS * CELL_H)) * 100}%` }}
                  >
                    {e.label}
                  </span>
                )
              })}
              {nodes.map((n) => (
                <div
                  key={n.id}
                  className="absolute flex items-center justify-center p-3"
                  style={{ left: `${(n.col / COLS) * 100}%`, top: `${(n.row / ROWS) * 100}%`, width: `${100 / COLS}%`, height: `${100 / ROWS}%` }}
                >
                  <button
                    type="button"
                    aria-pressed={n.id === node.id}
                    onClick={() => setPicked(n.id)}
                    className={cn(
                      't-small flex h-16 w-full cursor-pointer flex-col items-center justify-center rounded-tile border bg-inset px-2 text-center hover:bg-line',
                      n.id === node.id ? 'border-2 border-brand' : n.proposed ? 'border-dashed border-muted-ink' : 'border-line',
                      n.external && 'bg-surface',
                    )}
                  >
                    <span className="font-semibold">{n.name}</span>
                    <span className="text-muted-ink">{n.kind}</span>
                  </button>
                </div>
              ))}
            </div>
          </div>
          <NodeDetail node={node} />
        </div>
      )}
    </LaterCard>
  )
}

function IncidentsTab({ slug }: { slug: string }) {
  const items = dataFor(slug).incidents
  return (
    <LaterCard title="What went wrong here?" detail={previewProjectData.source} count={items.length}>
      {items.length === 0 ? (
        <Empty>No incidents recorded for this project.</Empty>
      ) : (
        <ul className="m-0 list-none p-0">
          {items.map((i) => (
            <li key={i.title}>
              <CardRow lines={2} className="grid-cols-[minmax(0,1fr)_auto]">
                <div className="flex min-w-0 flex-col">
                  <span className="t-body truncate">{i.title}</span>
                  <span className="t-small truncate text-muted-ink">
                    {i.when}, from {i.source}
                  </span>
                </div>
                <StatusChip label={i.status} tone={i.tone} />
              </CardRow>
            </li>
          ))}
        </ul>
      )}
    </LaterCard>
  )
}

function DeploymentsTab({ slug }: { slug: string }) {
  const items = dataFor(slug).deployments
  return (
    <LaterCard title="What was deployed, and where?" detail={previewProjectData.source} count={items.length}>
      {items.length === 0 ? (
        <Empty>No deployments recorded for this project.</Empty>
      ) : (
        <ul className="m-0 list-none p-0">
          {items.map((d) => (
            <li key={d.title}>
              <CardRow lines={2} className="grid-cols-[minmax(0,1fr)_auto]">
                <div className="flex min-w-0 flex-col">
                  <span className="t-body truncate">{d.title}</span>
                  <span className="t-small truncate text-muted-ink">
                    {d.when}, from {d.source}
                  </span>
                </div>
                <span className="t-small font-semibold">{d.environment}</span>
              </CardRow>
            </li>
          ))}
        </ul>
      )}
    </LaterCard>
  )
}

function LearningTab({ slug }: { slug: string }) {
  const items = dataFor(slug).learning
  return (
    <LaterCard title="What did this project teach?" detail={previewProjectData.source} count={items.length}>
      {items.length === 0 ? (
        <Empty>No learning linked to this project yet.</Empty>
      ) : (
        <ul className="m-0 list-none p-0">
          {items.map((l) => (
            <li key={l.title}>
              <CardRow lines={2} className="grid-cols-1">
                <div className="flex min-w-0 flex-col">
                  <span className="t-body truncate">{l.title}</span>
                  <span className="t-small truncate text-muted-ink">{l.detail}</span>
                </div>
              </CardRow>
            </li>
          ))}
        </ul>
      )}
    </LaterCard>
  )
}

export function LaterTabContent({ tab, slug }: { tab: LaterTab; slug: string }) {
  switch (tab) {
    case 'timeline':
      return <TimelineTab slug={slug} />
    case 'architecture':
      return <ArchitectureTab slug={slug} />
    case 'incidents':
      return <IncidentsTab slug={slug} />
    case 'deployments':
      return <DeploymentsTab slug={slug} />
    case 'learning':
      return <LearningTab slug={slug} />
  }
}

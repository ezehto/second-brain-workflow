import { Link } from 'react-router'
import { Card, CardHead, InsetItem } from '@/components/Card'
import { Button } from '@/components/ui/button'
import { TONE_TEXT } from '@/domain/status'
import { noteHref, routes } from '@/lib/routes'
import { previewWorkflow } from '@/preview'

/** Preview: needs a workflow stage on each task, which the plan does not have yet. */
export function WorkflowStages() {
  const { stages, rework, source } = previewWorkflow
  return (
    <Card>
      <CardHead title="Where work sits across projects" note={source}>
        <Button asChild variant="secondary" size="sm">
          <Link to={routes.workflow}>Open workflow</Link>
        </Button>
      </CardHead>
      <ul className="m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(120px,1fr))] gap-2.5 px-5 pb-4">
        {stages.map((s) => (
          <li key={s.label}>
            <InsetItem className="flex h-full flex-col px-3.5 py-3">
              <span className={`num text-2xl leading-tight font-extrabold ${s.tone === 'ink' ? 'text-ink' : TONE_TEXT[s.tone]}`}>{s.count}</span>
              <span className="text-[13px] font-semibold">{s.label}</span>
            </InsetItem>
          </li>
        ))}
      </ul>
      <p className="m-0 px-5 pb-[18px]">
        <span className="font-bold text-status-blocked">{rework.count} in rework.</span>{' '}
        <Link to={noteHref(rework.taskPath)} className="linkbtn font-medium">
          {rework.taskTitle}
        </Link>{' '}
        <span className="text-muted-ink">{rework.why}</span>
      </p>
    </Card>
  )
}

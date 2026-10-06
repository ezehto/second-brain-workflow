import { Link } from 'react-router'
import { Card, CardHead } from '@/components/Card'
import { PreviewBadge } from '@/components/PreviewBadge'
import { Button } from '@/components/ui/button'
import { TONE_TEXT } from '@/domain/status'
import { routes } from '@/lib/routes'
import { useProjectHref } from '@/lib/projectContext'
import { previewWorkflow } from '@/preview'

/** Preview: where work sits across the six stages, compact, with the rework line. Needs a stage on each task. */
export function WorkflowStrip() {
  const href = useProjectHref()
  const { stages, rework, source } = previewWorkflow
  return (
    <Card aria-label="Workflow stages">
      <CardHead title="Where does work sit?">
        <PreviewBadge detail={source} />
        <Button asChild variant="secondary" size="sm">
          <Link to={href.link(routes.workflow)}>Open workflow</Link>
        </Button>
      </CardHead>
      <ul className="m-0 flex list-none flex-wrap gap-x-6 gap-y-1 border-t border-line px-3 py-2">
        {stages.map((s) => (
          <li key={s.label} className="flex items-baseline gap-2">
            <span className={`num t-panel font-bold ${s.tone === 'ink' ? 'text-ink' : TONE_TEXT[s.tone]}`}>{s.count}</span>
            <span className="t-small text-muted-ink">{s.label}</span>
          </li>
        ))}
      </ul>
      <p className="t-small m-0 border-t border-line px-3 py-2">
        <span className="font-semibold text-status-blocked">{rework.count} in rework.</span>{' '}
        <Link to={href.note(rework.taskPath)} className="linkbtn t-small">
          {rework.taskTitle}
        </Link>{' '}
        <span className="text-muted-ink">{rework.why}</span>
      </p>
    </Card>
  )
}

/**
 * PREVIEW DATA. Nothing in this module is read from the vault or the Phase 1
 * API: meetings need Calendar (Phase 4), workflow stages need a stage on each
 * task (not in the plan yet), learning needs the upskilling notes (Phase 3),
 * Claude usage needs session logs (Phase 5), integrations arrive in Phase 4.
 *
 * Sections that render these values show the `source` text beside the heading
 * so it is clear on screen, as in code, that they are sample data. Replace a
 * value here with a real query when its phase ships, and delete the `source`.
 * Real Phase 1 data lives behind `src/api/`, never here.
 */
import type { IconName } from '@/components/Icon'
import type { StatusTone } from '@/domain/status'

export interface PreviewMeeting {
  time: string
  title: string
  length: string
}

export const previewMeetings: { source: string; items: PreviewMeeting[] } = {
  source: 'From Calendar, Phase 4. Sample data',
  items: [
    { time: '09:30', title: 'Daily standup with the team', length: '15 min' },
    { time: '11:00', title: 'UAT schedule with QA', length: '30 min' },
    { time: '15:00', title: 'Staging database refresh with infra', length: '30 min' },
  ],
}

export interface PreviewStage {
  label: string
  count: number
  tone: StatusTone | 'ink'
}

export const previewWorkflow: {
  source: string
  stages: PreviewStage[]
  rework: { count: number; taskTitle: string; taskPath: string; why: string }
} = {
  source: 'Needs a workflow stage on each task, not in the plan yet',
  stages: [
    { label: 'Understanding', count: 2, tone: 'ink' },
    { label: 'Planning', count: 3, tone: 'ink' },
    { label: 'Implementation', count: 3, tone: 'progress' },
    { label: 'Testing', count: 2, tone: 'ink' },
    { label: 'Review', count: 1, tone: 'review' },
    { label: 'Complete', count: 2, tone: 'done' },
  ],
  rework: {
    count: 3,
    taskTitle: 'Add retry with backoff to payment callback handler',
    taskPath: '02-Work/Tasks/Add retry with backoff to payment callback handler.md',
    why: 'Two test failures of the same kind, back in implementation. Rework count 2. Two items are blocked.',
  },
}

export interface PreviewImprovement {
  icon: IconName
  label: string
  /** `emphasis` is shown in bold before the text, e.g. "Estimated:". */
  emphasis?: string
  text: string
  source: string
}

export const previewImproving: PreviewImprovement[] = [
  {
    icon: 'book',
    label: 'Learning',
    text: 'Idempotency and retries for payment callbacks. Next: write the failing test for the duplicate settlement row.',
    source: 'From the upskilling notes, Phase 3. Sample data',
  },
  {
    icon: 'bars',
    label: 'Claude usage',
    emphasis: 'Estimated:',
    text: '3 sessions and about 180k tokens today.',
    source: 'From Claude Code session logs, Phase 5',
  },
]

export interface PreviewIntegration {
  icon: IconName
  name: string
  purpose: string
  state: string
}

export const previewIntegrations: { source: string; items: PreviewIntegration[] } = {
  source: 'Where the data would come from',
  items: [
    { icon: 'ticket', name: 'Jira', purpose: 'Tickets and status changes', state: 'Not connected, Phase 4' },
    { icon: 'branch', name: 'GitLab', purpose: 'Commits and merge requests', state: 'Not connected, Phase 4' },
    { icon: 'calendar', name: 'Calendar', purpose: 'Meetings and times', state: 'Not connected, Phase 4' },
  ],
}

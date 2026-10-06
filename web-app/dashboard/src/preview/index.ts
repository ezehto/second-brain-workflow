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

/* ---------------------------------------------------------------------------
 * WP11 preview pages: Workflow, Timeline, Upskilling. Sample data only. The
 * derivation rules (stage mapping, rework counts, trails, roadmap weeks, the
 * skill chain) live beside the pages in `features/preview/`.
 * ------------------------------------------------------------------------- */

export const PREVIEW_PROJECTS: Record<string, string> = {
  loadup: 'LoadUp',
  ipp: 'IPP',
  'second-brain': 'Second Brain',
  'monitoring-dashboard': 'Monitoring Dashboard',
}

export type FailureKind = 'impl' | 'plan' | 'req'

/** One entry of an item's loop history: entered a stage, failed, or passed. */
export type LoopEntry =
  | { kind: 'stage'; stage: number; date: string; note?: string }
  | { kind: 'fail'; stage: number; date: string; cause: FailureKind; source: string; note: string }
  | { kind: 'pass'; stage: number; date: string; note?: string }

export interface PreviewWorkflowItem {
  id: string
  title: string
  project: string
  stage: number
  blocked: boolean
  blocker: string
  owner: string
  action: string
  history: LoopEntry[]
}

const enter = (stage: number, date: string, note?: string): LoopEntry => ({ kind: 'stage', stage, date, note })
const fail = (stage: number, date: string, cause: FailureKind, source: string, note: string): LoopEntry => ({ kind: 'fail', stage, date, cause, source, note })

export const previewWorkflowItems: { source: string; asOf: string; stageNames: string[]; items: PreviewWorkflowItem[] } = {
  source: 'Needs a workflow stage and a loop history on each task. Sample data',
  asOf: '2026-10-06',
  stageNames: ['Understanding', 'Planning', 'Implementation', 'Testing', 'Review', 'Complete'],
  items: [
    { id: 'retry', title: 'Add retry with backoff to payment callback handler', project: 'ipp', stage: 2, blocked: false, blocker: '', owner: 'You',
      action: 'Add the idempotency key check, then run the callback tests again. A third failure of this kind means replan.',
      history: [enter(1, '2026-10-02', 'Plan agreed: retry transient failures only'), enter(2, '2026-10-03'), enter(3, '2026-10-05'),
        fail(3, '2026-10-05', 'impl', 'Test failed', 'The retried callback wrote the settlement row twice.'),
        enter(2, '2026-10-05'), enter(3, '2026-10-06'),
        fail(3, '2026-10-06', 'impl', 'Test failed', 'The handler retried a business rejection.'),
        enter(2, '2026-10-06')] },
    { id: 'reserve', title: 'Reserve wallet balance before the provider call', project: 'ipp', stage: 1, blocked: false, blocker: '', owner: 'You',
      action: 'Update the plan: split reserve and confirm into two steps, record the decision, then implement.',
      history: [enter(1, '2026-09-28'), enter(2, '2026-10-01'), enter(3, '2026-10-02'), enter(4, '2026-10-05'),
        fail(4, '2026-10-05', 'plan', 'Review failed', 'The reservation is not released when the provider call times out. The plan assumed one transaction.'),
        enter(1, '2026-10-05')] },
    { id: 'otp-expiry', title: 'Expire OTP codes after the agreed window', project: 'loadup', stage: 0, blocked: true, blocker: 'Waiting for the expiry value: five or ten minutes', owner: 'Product owner',
      action: 'Get the expiry confirmed in writing, then replan.',
      history: [enter(1, '2026-10-01'), enter(2, '2026-10-02'), enter(3, '2026-10-05'),
        fail(3, '2026-10-05', 'req', 'Test failed', 'The test expects five minutes, the written requirement says ten. The acceptance criteria conflict.'),
        enter(0, '2026-10-05')] },
    { id: 'n1', title: 'Fix N+1 query on account listing', project: 'loadup', stage: 4, blocked: false, blocker: '', owner: 'Reviewer',
      action: 'Waiting on the second review pass. Due today.',
      history: [enter(1, '2026-09-30'), enter(2, '2026-10-01'), enter(3, '2026-10-02'), enter(4, '2026-10-03'),
        fail(4, '2026-10-03', 'impl', 'Review failed', 'The prefetch missed accounts without a wallet.'),
        enter(2, '2026-10-05'), enter(3, '2026-10-05'), enter(4, '2026-10-05')] },
    { id: 'otp-email', title: 'Investigate missing OTP email', project: 'loadup', stage: 2, blocked: false, blocker: '', owner: 'You',
      action: 'Compare the relay delivery logs with the send log for the affected accounts.',
      history: [enter(0, '2026-10-01'), enter(1, '2026-10-01'), enter(2, '2026-10-02')] },
    { id: 'sms', title: 'Confirm rate limit with SMS provider', project: 'loadup', stage: 0, blocked: true, blocker: 'Waiting on the provider account manager', owner: 'Provider account manager',
      action: 'Chase for the per-minute limit in writing. Due 5 Oct, overdue.',
      history: [enter(0, '2026-09-30')] },
    { id: 'loadtest', title: 'Load test wallet reservation path', project: 'ipp', stage: 3, blocked: true, blocker: 'Staging database refresh', owner: 'Infra',
      action: 'Ask infra for the refresh date.',
      history: [enter(1, '2026-10-01'), enter(2, '2026-10-02'), enter(3, '2026-10-05')] },
    { id: 'runbook', title: 'Write runbook for settlement file rerun', project: 'ipp', stage: 1, blocked: false, blocker: '', owner: 'You',
      action: 'Outline the rerun steps and the rollback, then get them checked by QA.',
      history: [enter(0, '2026-10-02'), enter(1, '2026-10-02')] },
    { id: 'rotate', title: 'Rotate staging API credentials', project: 'loadup', stage: 1, blocked: false, blocker: '', owner: 'You',
      action: 'Agree a rotation window with infra. Due 3 Oct, overdue.',
      history: [enter(1, '2026-09-29')] },
    { id: 'templates', title: 'Verify templates in Obsidian', project: 'second-brain', stage: 3, blocked: false, blocker: '', owner: 'You',
      action: 'Insert each of the six templates in Obsidian and compare with the design.',
      history: [enter(1, '2026-10-05'), enter(2, '2026-10-05'), enter(3, '2026-10-05')] },
    { id: 'readme', title: 'Draft Phase 1 README run instructions', project: 'second-brain', stage: 2, blocked: false, blocker: '', owner: 'You',
      action: 'Write run, stop, reindex and recover for the Compose stack.',
      history: [enter(1, '2026-10-05'), enter(2, '2026-10-05')] },
    { id: 'dupes', title: 'Reproduce duplicate settlement rows', project: 'ipp', stage: 5, blocked: false, blocker: '', owner: 'You',
      action: 'None.',
      history: [enter(0, '2026-10-01'), enter(1, '2026-10-01'), enter(2, '2026-10-02'), enter(3, '2026-10-04'), enter(4, '2026-10-05'),
        enter(5, '2026-10-05', 'Reproduced on staging: a retried callback wrote the row twice.')] },
    { id: 'docker', title: 'Enable Docker WSL integration', project: 'second-brain', stage: 5, blocked: false, blocker: '', owner: 'You',
      action: 'None.',
      history: [enter(1, '2026-10-01'), enter(2, '2026-10-01'), enter(3, '2026-10-02'), enter(5, '2026-10-02', 'docker compose runs in WSL.')] },
  ],
}

export type TimelineSource = 'vault' | 'jira' | 'gitlab' | 'calendar'
export type TimelineStatus = 'open' | 'review' | 'blocked' | 'done' | 'na'

export interface PreviewTimelineEvent {
  id: string
  date: string
  time: string
  type: string
  title: string
  projects: string[]
  source: TimelineSource
  status: TimelineStatus
  ref?: string
  note?: string
  file?: string
  /** Text quoted from the external system. External content is data, shown as a quote. */
  quote?: string
  /** Which correlation trail the event belongs to, and whether it is the trail's anchor row. */
  trail?: string
  suggestion?: boolean
}

export interface PreviewTrail {
  basis: string
  steps: { label: string; value: string; note: string; pending?: boolean }[]
  anchorType: string
}

const ev = (
  id: string, date: string, time: string, type: string, title: string, projects: string[], source: TimelineSource, status: TimelineStatus,
  more: Partial<PreviewTimelineEvent> = {},
): PreviewTimelineEvent => ({ id, date, time, type, title, projects, source, status, ...more })

export const previewTimeline: {
  source: string
  asOf: string
  selectedId: string
  eventTypes: Record<string, string>
  sourceLabels: Record<TimelineSource, string>
  events: PreviewTimelineEvent[]
  trails: Record<string, PreviewTrail>
  suggestion: { eventId: string; text: string; targetEvent: string; file: string; basis: string }
} = {
  source: 'Jira, GitLab and Calendar arrive in Phase 4; vault events are read from file times. Sample data',
  asOf: '2026-10-06',
  selectedId: 'a3',
  eventTypes: {
    'task-created': 'Task created', 'task-completed': 'Task completed', standup: 'Standup', decision: 'Decision', lesson: 'Lesson',
    document: 'Document', meeting: 'Meeting', ticket: 'Ticket updated', commit: 'Commit', mr: 'Merge request', review: 'Code review',
    deploy: 'Deployment', incident: 'Incident', learning: 'Learning',
  },
  sourceLabels: { vault: 'Vault', jira: 'Jira', gitlab: 'GitLab', calendar: 'Calendar' },
  events: [
    ev('a1', '2026-10-06', '13:05', 'mr', 'Add retry with backoff to payment callback handler', ['ipp'], 'gitlab', 'review', { ref: '!214', note: 'Opened by you. Pipeline is running, no deployment yet.', trail: 'A' }),
    ev('a2', '2026-10-06', '12:48', 'commit', 'Retry transient failures only, never on a business rejection', ['ipp'], 'gitlab', 'na', { ref: 'c3f9a1e', note: 'Pushed to feature/ipp-callback-retry.' }),
    ev('a3', '2026-10-06', '11:20', 'ticket', 'OTP emails: relay log sample added to the ticket', ['loadup'], 'jira', 'open', { ref: 'LUP-482', note: 'A comment was added by QA with the relay delivery log sample.', quote: 'Relay log sample attached. Please also rotate the staging credentials today.' }),
    ev('a4', '2026-10-06', '10:50', 'deploy', 'Account listing fix deployed to staging', ['loadup'], 'gitlab', 'done', { ref: 'staging', note: 'Deployed from pipeline #4412 after merge request !209.', trail: 'B' }),
    ev('a5', '2026-10-06', '10:00', 'meeting', 'Callback retry walkthrough with QA', ['ipp'], 'calendar', 'na', { note: 'Thirty minutes. No meeting note exists yet.' }),
    ev('a6', '2026-10-06', '09:15', 'learning', 'Practice: idempotency keys on a callback handler', ['ipp'], 'vault', 'na', { file: '06-Upskilling/Practice/Practice idempotency keys on a callback handler.md' }),
    ev('a7', '2026-10-06', '08:55', 'task-created', 'Clarify OTP expiry requirement', ['loadup'], 'vault', 'open', { file: '02-Work/Tasks/Clarify OTP expiry requirement.md', note: 'Written by hand in Obsidian, in the inbox.' }),
    ev('a8', '2026-10-06', '08:30', 'standup', 'Standup 2026-10-06', ['loadup', 'ipp'], 'vault', 'na', { file: '01-Daily/2026/2026-10-06.md' }),
    ev('b1', '2026-10-05', '17:42', 'mr', 'Prefetch wallet balances on the account listing', ['loadup'], 'gitlab', 'review', { ref: '!209', note: 'Opened by you for the N+1 fix. The linked trail is under the deployment on Oct 6.' }),
    ev('b2', '2026-10-05', '17:05', 'decision', 'Use idempotency keys on payment callbacks', ['ipp'], 'vault', 'open', { file: '05-Knowledge/Decisions/Use idempotency keys on payment callbacks.md', note: 'Status proposed.' }),
    ev('b3', '2026-10-05', '16:55', 'lesson', 'A retry on a business rejection duplicates the send', ['ipp'], 'vault', 'na', { file: '05-Knowledge/Lessons/A retry on a business rejection duplicates the send.md' }),
    ev('b4', '2026-10-05', '16:48', 'task-completed', 'Reproduce duplicate settlement rows', ['ipp'], 'vault', 'done', { file: '02-Work/Tasks/Reproduce duplicate settlement rows.md' }),
    ev('b5', '2026-10-05', '16:20', 'review', 'Reviewed callback logging, approved', ['ipp'], 'gitlab', 'done', { ref: '!207', note: 'You approved with two comments on log fields.' }),
    ev('b6', '2026-10-05', '14:30', 'ticket', 'Load test wallet reservation: blocked on staging database refresh', ['ipp'], 'jira', 'blocked', { ref: 'IPP-305', note: 'Status moved to Blocked. Waiting on infra.' }),
    ev('b7', '2026-10-05', '12:00', 'decision', 'Poll the vault instead of file watching', ['second-brain'], 'vault', 'done', { file: '05-Knowledge/Decisions/Poll the vault instead of file watching.md', note: 'Status accepted.' }),
    ev('b8', '2026-10-05', '09:15', 'ticket', 'Confirm SMS rate limit: waiting on the provider', ['loadup'], 'jira', 'blocked', { ref: 'LUP-479', note: 'Waiting on the provider account manager.' }),
    ev('b9', '2026-10-05', '09:00', 'standup', 'Standup 2026-10-05', ['loadup', 'ipp'], 'vault', 'na', { file: '01-Daily/2026/2026-10-05.md' }),
    ev('c1', '2026-10-02', '16:10', 'task-created', 'Write runbook for settlement file rerun', ['ipp'], 'vault', 'open', { file: '02-Work/Tasks/Write runbook for settlement file rerun.md', suggestion: true }),
    ev('c2', '2026-10-02', '15:10', 'decision', 'Keep OTP email on the existing SMTP relay', ['loadup'], 'vault', 'done', { file: '05-Knowledge/Decisions/Keep OTP email on the existing SMTP relay.md', note: 'Status accepted.' }),
    ev('c3', '2026-10-02', '11:00', 'meeting', 'Provider call: OTP relay logs', ['loadup'], 'calendar', 'na', { note: 'Provider account manager and you. Follow-up: send the relay log sample.' }),
    ev('c4', '2026-10-02', '09:30', 'task-completed', 'Enable Docker WSL integration', ['second-brain'], 'vault', 'done', { file: '02-Work/Tasks/Enable Docker WSL integration.md' }),
    ev('c5', '2026-10-02', '09:00', 'standup', 'Standup 2026-10-02', ['loadup', 'ipp', 'second-brain'], 'vault', 'na', { file: '01-Daily/2026/2026-10-02.md' }),
    ev('d1', '2026-10-01', '18:00', 'lesson', 'Check the provider status page before debugging delivery', ['loadup'], 'vault', 'na', { file: '05-Knowledge/Lessons/Check the provider status page before debugging delivery.md' }),
    ev('d2', '2026-10-01', '14:20', 'document', 'Incident report: OTP emails delayed on 30 September', ['loadup'], 'vault', 'review', { file: '02-Work/Incidents/OTP emails delayed on 30 September.md', note: 'Incident report, needs review.' }),
    ev('d3', '2026-10-01', '10:10', 'commit', 'Log relay delivery status for each OTP send', ['loadup'], 'gitlab', 'na', { ref: 'a81d20b', note: 'Delivery logging that the SMTP relay decision called for.' }),
    ev('d4', '2026-10-01', '09:00', 'standup', 'Standup 2026-10-01', ['loadup'], 'vault', 'na', { file: '01-Daily/2026/2026-10-01.md' }),
    ev('e1', '2026-09-30', '15:10', 'incident', 'OTP emails delayed for some sign-ins', ['loadup'], 'jira', 'done', { ref: 'INC-77', note: 'Resolved after the provider cleared its own delay. The report is a draft in review.' }),
    ev('e2', '2026-09-30', '14:20', 'task-created', 'Confirm rate limit with SMS provider', ['loadup'], 'vault', 'open', { file: '02-Work/Tasks/Confirm rate limit with SMS provider.md' }),
    ev('e3', '2026-09-30', '11:00', 'meeting', 'Vault structure review', ['second-brain'], 'calendar', 'na', { note: 'Folder layout and templates. No meeting note exists yet.' }),
    ev('e4', '2026-09-30', '10:00', 'ticket', 'Retry callbacks on transient failure: moved to In progress', ['ipp'], 'jira', 'open', { ref: 'IPP-298', note: 'Start of the callback retry work.' }),
    ev('e5', '2026-09-30', '09:00', 'standup', 'Standup 2026-09-30', ['loadup', 'ipp'], 'vault', 'na', { file: '01-Daily/2026/2026-09-30.md' }),
    ev('f1', '2026-09-29', '16:30', 'task-created', 'Rotate staging API credentials', ['loadup'], 'vault', 'open', { file: '02-Work/Tasks/Rotate staging API credentials.md' }),
    ev('f2', '2026-09-29', '15:00', 'learning', 'Notes: Docker bind mounts on a Windows drive', ['second-brain'], 'vault', 'na', { file: '06-Upskilling/Learning/Notes Docker bind mounts on a Windows drive.md' }),
    ev('f3', '2026-09-29', '11:30', 'meeting', 'Settlement file rerun review', ['ipp'], 'calendar', 'na', { note: 'Calendar title only. The attendee notes are not read.' }),
    ev('f4', '2026-09-29', '09:00', 'standup', 'Standup 2026-09-29', ['loadup', 'ipp'], 'vault', 'na', { file: '01-Daily/2026/2026-09-29.md' }),
  ],
  trails: {
    A: {
      anchorType: 'mr',
      basis: 'High confidence: the issue key IPP-298 is in the branch name and the merge request title.',
      steps: [
        { label: 'Jira issue', value: 'IPP-298', note: 'in progress' },
        { label: 'Branch', value: 'feature/ipp-callback-retry', note: '' },
        { label: 'Merge request', value: '!214', note: 'in review' },
        { label: 'Pipeline', value: '#4431', note: 'running' },
        { label: 'Deployment', value: 'N/A', note: 'none yet', pending: true },
      ],
    },
    B: {
      anchorType: 'deploy',
      basis: 'High confidence: the issue key LUP-471 is in the branch name, the merge request title and the pipeline.',
      steps: [
        { label: 'Jira issue', value: 'LUP-471', note: 'N+1 on account listing' },
        { label: 'Branch', value: 'fix/LUP-471-account-listing', note: '' },
        { label: 'Merge request', value: '!209', note: 'Oct 5' },
        { label: 'Pipeline', value: '#4412', note: 'passed' },
        { label: 'Deployment', value: 'staging', note: 'Oct 6 10:50' },
      ],
    },
  },
  suggestion: {
    eventId: 'c1',
    text: 'Settlement file rerun review (meeting, Sep 29) may relate to this task.',
    targetEvent: 'f3',
    file: '02-Work/Tasks/Write runbook for settlement file rerun.md',
    basis: 'Unconfirmed: the titles share "settlement file rerun" and both are in IPP. Nothing else links them.',
  },
}

export interface PreviewSkill {
  id: string
  category: string
  name: string
  level: 'Aware' | 'Practicing' | 'Applied' | 'Can teach'
  latest: { title: string; date: string } | null
  gap: string
  project: string
  /** Seven steps: problem, gap, learning, practice, applied, review, lesson. An empty string is a missing step. */
  chain: string[]
}

export interface PreviewLearningNote {
  title: string
  kind: 'learning' | 'practice' | 'applied'
  date: string
  skill: string
  project?: string
}

export interface PreviewRecommendation {
  id: string
  skillId: string
  title: string
  project: string
  why: string
  fit: string
  evidence: { kind: string; title: string }[]
}

export const previewUpskilling: {
  source: string
  asOf: string
  roadmapStart: string
  currentWeek: number
  themes: string[]
  weekStates: Record<number, 'done' | 'partly'>
  checklist: { id: string; text: string; done: boolean; note: string }[]
  skills: PreviewSkill[]
  notes: PreviewLearningNote[]
  recommendations: PreviewRecommendation[]
} = {
  source: 'Needs the 06-Upskilling notes and the roadmap. Sample data',
  asOf: '2026-10-06',
  roadmapStart: '2026-08-31',
  currentWeek: 6,
  themes: [
    'API design: resources and naming', 'API design: errors and pagination', 'Database performance: reading query plans',
    'Database performance: N+1 and indexes', 'Observability: logs and correlation ids', 'Idempotency and retries',
    'Distributed systems reliability: timeouts', 'Distributed systems reliability: queues and ordering', 'Observability: metrics and alerts',
    'System design: estimation', 'System design: data and consistency', 'System design: a full design review',
    'Security basics: secrets and authentication', 'Security basics: rate limits and abuse', 'Technical writing: decision records',
    'Technical writing: proposals', 'Review and retrospective',
  ],
  weekStates: { 1: 'done', 2: 'done', 3: 'done', 4: 'partly', 5: 'done' },
  checklist: [
    { id: 'c1', text: 'Read about idempotency keys and dedup tables', done: true, note: 'Idempotent consumers and dedup tables' },
    { id: 'c2', text: 'Sketch a key store with an expiry', done: true, note: 'Sketch idempotency key store with expiry' },
    { id: 'c3', text: 'Classify callback failures before retrying, then apply it to the handler', done: false, note: '' },
    { id: 'c4', text: 'Write the retry rules down as a lesson', done: true, note: 'A retry on a business rejection duplicates the send' },
    { id: 'c5', text: 'Sunday review: what was learned, practiced and applied', done: false, note: '' },
  ],
  notes: [
    { title: 'Idempotency keys, the basics', kind: 'learning', date: '2026-09-02', skill: 'Idempotency' },
    { title: 'Retry and backoff patterns', kind: 'learning', date: '2026-09-04', skill: 'Retries and backoff' },
    { title: 'HTTP API design: resource naming', kind: 'learning', date: '2026-09-08', skill: 'HTTP resource design' },
    { title: 'Design a paginated listing endpoint', kind: 'practice', date: '2026-09-11', skill: 'HTTP resource design' },
    { title: 'PostgreSQL EXPLAIN reading', kind: 'learning', date: '2026-09-15', skill: 'PostgreSQL indexing' },
    { title: 'Read plans for three slow queries', kind: 'practice', date: '2026-09-18', skill: 'PostgreSQL indexing' },
    { title: 'Query planning and N+1', kind: 'learning', date: '2026-09-22', skill: 'Query performance' },
    { title: 'Reproduce N+1 with query count', kind: 'practice', date: '2026-09-24', skill: 'Query performance' },
    { title: 'Structured logging and correlation ids', kind: 'learning', date: '2026-09-29', skill: 'Structured logging' },
    { title: 'Add correlation id to OTP send log', kind: 'practice', date: '2026-10-01', skill: 'Structured logging' },
    { title: 'Prefetch wallet balance on account listing', kind: 'applied', date: '2026-10-02', skill: 'Query performance', project: 'LoadUp' },
    { title: 'Idempotent consumers and dedup tables', kind: 'learning', date: '2026-10-05', skill: 'Idempotency' },
    { title: 'Sketch idempotency key store with expiry', kind: 'practice', date: '2026-10-06', skill: 'Idempotency' },
    { title: 'Classify callback failures before retrying', kind: 'applied', date: '2026-10-06', skill: 'Retries and backoff', project: 'IPP' },
  ],
  skills: [
    { id: 'idempotency', category: 'Reliability', name: 'Idempotency', level: 'Practicing', latest: { title: 'Sketch idempotency key store with expiry', date: '2026-10-06' }, gap: 'Duplicate settlement rows', project: 'IPP',
      chain: ['Reproduce duplicate settlement rows', 'Idempotency', 'Idempotent consumers and dedup tables', 'Sketch idempotency key store with expiry', '', '', 'A retry on a business rejection duplicates the send'] },
    { id: 'retries', category: 'Reliability', name: 'Retries and backoff', level: 'Practicing', latest: { title: 'Classify callback failures before retrying', date: '2026-10-06' }, gap: 'A retry duplicated a send', project: 'IPP',
      chain: ['Reproduce duplicate settlement rows', 'Retries and backoff', 'Retry and backoff patterns', '', 'Classify callback failures before retrying', '', 'A retry on a business rejection duplicates the send'] },
    { id: 'http', category: 'API design', name: 'HTTP resource design', level: 'Practicing', latest: { title: 'Design a paginated listing endpoint', date: '2026-09-11' }, gap: '', project: '',
      chain: ['', '', 'HTTP API design: resource naming', 'Design a paginated listing endpoint', '', '', ''] },
    { id: 'errors', category: 'API design', name: 'Error contracts', level: 'Aware', latest: null, gap: '', project: '', chain: ['', '', '', '', '', '', ''] },
    { id: 'queryperf', category: 'Database', name: 'Query performance', level: 'Applied', latest: { title: 'Prefetch wallet balance on account listing', date: '2026-10-02' }, gap: 'One query per row', project: 'LoadUp',
      chain: ['Fix N+1 query on account listing', 'Query performance', 'Query planning and N+1', 'Reproduce N+1 with query count', 'Prefetch wallet balance on account listing', '', ''] },
    { id: 'indexing', category: 'Database', name: 'PostgreSQL indexing', level: 'Practicing', latest: { title: 'Read plans for three slow queries', date: '2026-09-18' }, gap: '', project: '',
      chain: ['', '', 'PostgreSQL EXPLAIN reading', 'Read plans for three slow queries', '', '', ''] },
    { id: 'logging', category: 'Observability', name: 'Structured logging', level: 'Practicing', latest: { title: 'Add correlation id to OTP send log', date: '2026-10-01' }, gap: 'Two hours lost to missing delivery logs', project: 'LoadUp',
      chain: ['Investigate missing OTP email', 'Structured logging', 'Structured logging and correlation ids', 'Add correlation id to OTP send log', '', '', 'Check the provider status page before debugging delivery'] },
    { id: 'alerts', category: 'Observability', name: 'Alert design', level: 'Aware', latest: null, gap: '', project: '', chain: ['', '', '', '', '', '', ''] },
    { id: 'spikes', category: 'System design', name: 'Spikes before design', level: 'Applied', latest: { title: 'Measure the mount before building on it', date: '2026-10-03' }, gap: '', project: '',
      chain: ['', '', '', '', 'Poll the vault instead of file watching', '', 'Measure the mount before building on it'] },
    { id: 'runbooks', category: 'Writing', name: 'Runbooks', level: 'Aware', latest: null, gap: 'Settlement rerun has no runbook', project: 'IPP',
      chain: ['Write runbook for settlement file rerun', 'Runbooks', '', '', '', '', ''] },
    { id: 'adrs', category: 'Writing', name: 'Decision records', level: 'Practicing', latest: { title: 'Use idempotency keys on payment callbacks', date: '2026-10-05' }, gap: '', project: '',
      chain: ['', '', '', '', 'Use idempotency keys on payment callbacks', '', ''] },
    { id: 'secrets', category: 'Security', name: 'Secrets rotation', level: 'Aware', latest: null, gap: 'Staging credentials past rotation date', project: 'LoadUp',
      chain: ['Rotate staging API credentials', 'Secrets rotation', '', '', '', '', ''] },
    { id: 'ratelimit', category: 'Security', name: 'Rate limiting', level: 'Aware', latest: null, gap: 'Provider rate limit unknown', project: 'LoadUp',
      chain: ['Confirm rate limit with SMS provider', 'Rate limiting', '', '', '', '', ''] },
  ],
  recommendations: [
    { id: 'r1', skillId: 'idempotency', title: 'Idempotency keys for payment callbacks', project: 'IPP',
      why: 'A retried callback wrote the same settlement row twice. The fix is only a proposed decision so far, and you have read about it but not applied it.',
      fit: 'Matches this week: Idempotency and retries.',
      evidence: [{ kind: 'Task', title: 'Reproduce duplicate settlement rows' }, { kind: 'Lesson', title: 'A retry on a business rejection duplicates the send' }, { kind: 'Decision', title: 'Use idempotency keys on payment callbacks' }] },
    { id: 'r2', skillId: 'queryperf', title: 'Read the query plan before merging the N+1 fix', project: 'LoadUp',
      why: 'The N+1 fix on the account listing is in review. You counted queries but have not read the plan for the new prefetch query.',
      fit: 'Revisits week 3, reading query plans.',
      evidence: [{ kind: 'Task', title: 'Fix N+1 query on account listing' }, { kind: 'Practice', title: 'Reproduce N+1 with query count' }] },
    { id: 'r3', skillId: 'logging', title: 'Correlation ids across the OTP send path', project: 'LoadUp',
      why: 'Some OTP emails never arrive and two hours went into the wrong logs. A correlation id would show where each send stopped.',
      fit: 'Pulls forward part of week 9, metrics and alerts.',
      evidence: [{ kind: 'Task', title: 'Investigate missing OTP email' }, { kind: 'Lesson', title: 'Check the provider status page before debugging delivery' }] },
  ],
}

export interface PreviewStandupReference {
  kind: 'ticket' | 'meeting'
  ref: string
  text: string
}

export const previewStandupReferences: { source: string; items: PreviewStandupReference[] } = {
  source: 'Tickets come from Jira and meetings from Calendar, Phase 4. Sample data, not written to the note',
  items: [
    { kind: 'ticket', ref: 'LD-482', text: 'OTP delivery gap, moved to In Review' },
    { kind: 'meeting', ref: '11:00', text: 'UAT schedule with QA' },
  ],
}

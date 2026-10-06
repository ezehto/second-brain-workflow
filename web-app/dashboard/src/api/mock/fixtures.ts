import type { IndexProblemCategory, IndexProblem, NoteSummary, Priority, ProjectSummary } from '../types'

/**
 * Sample vault, ported from the approved prototype (docs/design/prototype/
 * Main.dc.html). Dates are absolute; the mock client takes "today" as an
 * option so the same data can be read on another day in tests.
 */
export const FIXTURE_TODAY = '2026-10-06'

/** Local time with the vault offset, from the prototype's `YYYY-MM-DD HH:mm`. */
const at = (stamp: string) => `${stamp.replace(' ', 'T')}:00+08:00`

interface TaskRow {
  t: string
  p: string
  s: string
  pr: Priority | ''
  due: string
  by?: string
  c: string
  m: string
  noId?: boolean
}

const TASKS: TaskRow[] = [
  { t: 'Investigate missing OTP email', p: 'loadup', s: 'in-progress', pr: 'high', due: '2026-10-06', c: '2026-10-01', m: '2026-10-06 11:20' },
  { t: 'Add retry with backoff to payment callback handler', p: 'ipp', s: 'in-progress', pr: 'high', due: '2026-10-07', c: '2026-10-02', m: '2026-10-06 13:05' },
  { t: 'Fix N+1 query on account listing', p: 'loadup', s: 'review', pr: 'medium', due: '2026-10-06', c: '2026-09-30', m: '2026-10-05 17:42' },
  { t: 'Write runbook for settlement file rerun', p: 'ipp', s: 'planned', pr: 'medium', due: '2026-10-06', c: '2026-10-02', m: '2026-10-02 16:10' },
  { t: 'Rotate staging API credentials', p: 'loadup', s: 'planned', pr: 'high', due: '2026-10-03', c: '2026-09-29', m: '2026-09-29 10:02' },
  { t: 'Confirm rate limit with SMS provider', p: 'loadup', s: 'blocked', pr: 'high', due: '2026-10-05', by: 'Waiting on the provider account manager', c: '2026-09-30', m: '2026-10-05 09:15' },
  { t: 'Load test wallet reservation path', p: 'ipp', s: 'blocked', pr: 'medium', due: '2026-10-09', by: 'Staging database refresh', c: '2026-10-01', m: '2026-10-05 14:30' },
  { t: 'Verify templates in Obsidian', p: 'second-brain', s: 'planned', pr: 'medium', due: '2026-10-08', c: '2026-10-05', m: '2026-10-05 18:20' },
  { t: 'Draft Phase 1 README run instructions', p: 'second-brain', s: 'planned', pr: 'low', due: '', c: '2026-10-05', m: '2026-10-05 18:25' },
  { t: 'Add alert for callback queue depth', p: 'monitoring-dashboard', s: 'planned', pr: 'low', due: '2026-10-14', c: '2026-09-25', m: '2026-09-25 15:00' },
  { t: 'Reproduce duplicate settlement rows', p: 'ipp', s: 'done', pr: 'high', due: '2026-10-05', c: '2026-10-01', m: '2026-10-05 16:48' },
  { t: 'Enable Docker WSL integration', p: 'second-brain', s: 'done', pr: 'medium', due: '2026-10-02', c: '2026-10-01', m: '2026-10-02 09:30' },
  { t: 'Clarify OTP expiry requirement', p: 'loadup-v2', s: 'inbox', pr: '', due: '', c: '2026-10-06', m: '2026-10-06 08:55', noId: true },
  { t: 'Migrate cron jobs to scheduler', p: 'monitoring-dashboard', s: 'cancelled', pr: 'low', due: '', c: '2026-09-20', m: '2026-09-28 11:00' },
]

const blank = (): NoteSummary => ({
  id: null,
  path: '',
  type: 'note',
  title: '',
  status: null,
  priority: null,
  project: null,
  due: null,
  blocked_by: null,
  decided: null,
  tags: [],
  created: null,
  modified: '',
  parse_error: null,
})

/** A fake but stable `YYYYMMDDHHmmss` id from the created date. */
const idFrom = (created: string) => `${created.replace(/-/g, '')}093000`

export const taskFixtures = (): NoteSummary[] =>
  TASKS.map((x) => ({
    ...blank(),
    id: x.noId ? null : idFrom(x.c),
    path: `02-Work/Tasks/${x.t}.md`,
    type: 'task',
    title: x.t,
    status: x.s,
    priority: x.pr || null,
    project: x.p,
    due: x.due || null,
    blocked_by: x.by ?? null,
    created: x.c,
    modified: at(x.m),
  }))

export const projectFixtures = (): ProjectSummary[] =>
  [
    { slug: 'loadup', title: 'LoadUp', status: 'active', goal: 'Prepaid load top-up service: OTP sign-in and account listing work.', m: '2026-10-06 11:20' },
    { slug: 'ipp', title: 'IPP', status: 'active', goal: 'Payment processing: callbacks, settlement files and wallet reservation.', m: '2026-10-06 13:05' },
    { slug: 'second-brain', title: 'Second Brain', status: 'active', goal: 'This system: vault, Claude Code commands and the dashboard.', m: '2026-10-05 18:25' },
    { slug: 'monitoring-dashboard', title: 'Monitoring Dashboard', status: 'paused', goal: 'Alerts and queue visibility for the payment services.', m: '2026-09-28 11:00' },
  ].map((p) => ({
    slug: p.slug,
    title: p.title,
    path: `02-Work/Projects/${p.title}.md`,
    status: p.status,
    goal: p.goal,
    open_task_count: 0,
    modified: at(p.m),
  }))

export const projectNoteFixtures = (): NoteSummary[] =>
  projectFixtures().map((p) => ({
    ...blank(),
    id: idFrom('2026-09-15'),
    path: p.path,
    type: 'project',
    title: p.title,
    status: p.status,
    created: '2026-09-15',
    modified: p.modified,
  }))

const decisionRows = [
  { t: 'Keep OTP email on the existing SMTP relay', p: 'loadup', s: 'accepted', decided: '2026-10-02', c: '2026-10-01', m: '2026-10-02 15:10' },
  { t: 'Use idempotency keys on payment callbacks', p: 'ipp', s: 'proposed', decided: '', c: '2026-10-05', m: '2026-10-05 17:05' },
  { t: 'Poll the vault instead of file watching', p: 'second-brain', s: 'accepted', decided: '2026-10-05', c: '2026-10-05', m: '2026-10-05 12:00' },
  { t: 'Settlement reruns by full file replace', p: 'ipp', s: 'superseded', decided: '2026-09-18', c: '2026-09-18', m: '2026-10-05 17:06' },
]

export const decisionFixtures = (): NoteSummary[] =>
  decisionRows.map((x) => ({
    ...blank(),
    id: idFrom(x.c),
    path: `05-Knowledge/Decisions/${x.t}.md`,
    type: 'decision',
    title: x.t,
    status: x.s,
    project: x.p,
    decided: x.decided || null,
    created: x.c,
    modified: at(x.m),
  }))

const lessonRows = [
  { t: 'Check the provider status page before debugging delivery', p: 'loadup', tags: ['email', 'incident'], c: '2026-10-01', m: '2026-10-01 18:00' },
  { t: 'A retry on a business rejection duplicates the send', p: 'ipp', tags: ['payments', 'retries'], c: '2026-10-05', m: '2026-10-05 16:55' },
  { t: 'Measure the mount before building on it', p: 'second-brain', tags: ['docker', 'wsl'], c: '2026-10-03', m: '2026-10-03 14:20' },
]

export const lessonFixtures = (): NoteSummary[] =>
  lessonRows.map((x) => ({
    ...blank(),
    id: idFrom(x.c),
    path: `05-Knowledge/Lessons/${x.t}.md`,
    type: 'lesson',
    title: x.t,
    status: 'active',
    project: x.p,
    tags: x.tags,
    created: x.c,
    modified: at(x.m),
  }))

const captureRows = [
  { text: 'todo: renew the staging TLS certificate before the 20th', hm: '0912' },
  { text: 'decided to keep the OTP sender on the existing relay until the provider contract is signed', hm: '1040' },
  { text: 'Idempotency keys on the callback handler would have prevented the duplicate rows', hm: '1158' },
  { text: 'Should the standup list show week numbers?', hm: '1326' },
]

/** Capture file names follow plan section 2.5, rule 9. */
export const captureName = (date: string, hm: string, text: string) =>
  `${date} ${hm} ${text.split(/\s+/).slice(0, 8).join(' ')}`

export const captureFixtures = (): NoteSummary[] =>
  captureRows.map((x) => ({
    ...blank(),
    id: `${FIXTURE_TODAY.replace(/-/g, '')}${x.hm}00`,
    path: `00-Inbox/${captureName(FIXTURE_TODAY, x.hm, x.text)}.md`,
    type: 'capture',
    title: captureName(FIXTURE_TODAY, x.hm, x.text),
    status: 'inbox',
    created: FIXTURE_TODAY,
    modified: at(`${FIXTURE_TODAY} ${x.hm.slice(0, 2)}:${x.hm.slice(2)}`),
  }))

export const dailyFixtures = (): NoteSummary[] =>
  ['2026-10-05', '2026-10-02', '2026-10-01'].map((d) => ({
    ...blank(),
    id: idFrom(d),
    path: `01-Daily/${d.slice(0, 4)}/${d}.md`,
    type: 'daily',
    title: d,
    created: d,
    modified: at(`${d} 17:50`),
  }))

/** The six-section bodies of the past daily notes, from the prototype's `dailies()` data. */
const DAILY_SECTIONS: Record<string, [string, string[]][]> = {
  '2026-10-05': [
    ['Done', ['- [x] [[Reproduce duplicate settlement rows]]', '- [x] Reviewed the callback logging merge request']],
    ['Today', ['- [ ] [[Investigate missing OTP email]]', '- [ ] [[Fix N+1 query on account listing]]', '- [ ] Reply to QA about the UAT schedule']],
    ['Blockers', ['- [[Confirm rate limit with SMS provider]] (blocked by: Waiting on the provider account manager)']],
    ['Decisions / Updates', ['- [[Poll the vault instead of file watching]] accepted']],
    ['Follow-ups', ['- [ ] Ask infra for the staging database refresh date']],
    ['Related Tasks / Projects', ['- [[IPP]]', '- [[LoadUp]]']],
  ],
  '2026-10-02': [
    ['Done', ['- [x] [[Enable Docker WSL integration]]']],
    ['Today', ['- [ ] [[Investigate missing OTP email]]', '- [ ] [[Reproduce duplicate settlement rows]]']],
    ['Blockers', []],
    ['Decisions / Updates', ['- [[Keep OTP email on the existing SMTP relay]] accepted']],
    ['Follow-ups', ['- [x] Send the relay log sample to the provider']],
    ['Related Tasks / Projects', ['- [[IPP]]', '- [[LoadUp]]', '- [[Second Brain]]']],
  ],
  '2026-10-01': [
    ['Done', []],
    ['Today', ['- [ ] [[Investigate missing OTP email]]', '- [ ] Set up the new vault folders']],
    ['Blockers', []],
    ['Decisions / Updates', []],
    ['Follow-ups', []],
    ['Related Tasks / Projects', ['- [[LoadUp]]']],
  ],
}

/** Note body per daily-note path, for the mock client to serve. */
export const dailyBodies = (): Map<string, string> =>
  new Map(
    Object.entries(DAILY_SECTIONS).map(([date, sections]) => [
      `01-Daily/${date.slice(0, 4)}/${date}.md`,
      `# Standup - ${date}\n\n${sections.map(([heading, lines]) => `## ${heading}\n\n${lines.join('\n')}\n`).join('\n')}`,
    ]),
  )

/** Index problems, from the prototype's Index status page. */
export const indexProblemFixtures = (): Record<IndexProblemCategory, IndexProblem[]> => ({
  parse_errors: [{ path: '05-Knowledge/Lessons/Untitled.md', detail: 'Frontmatter: mapping values are not allowed here (line 3). Indexed as type note.' }],
  missing_ids: [
    { path: '02-Work/Tasks/Clarify OTP expiry requirement.md', detail: 'Created by hand in Obsidian without the template.' },
    { path: '02-Work/Projects/IPP kickoff notes.md', detail: 'No frontmatter.' },
  ],
  duplicate_ids: [{ path: '05-Knowledge/Lessons/Untitled.md', detail: 'Shares id 20261003142000 with Measure the mount before building on it.md (made with "Make a copy").' }],
  ambiguous_links: [{ path: '05-Knowledge/Lessons/A retry on a business rejection duplicates the send.md', detail: '[[Runbook]] matches 2 notes.' }],
  unknown_project_slugs: [{ path: '02-Work/Tasks/Clarify OTP expiry requirement.md', detail: 'project: loadup-v2 matches no project note.' }],
  duplicate_project_slugs: [],
  unknown_statuses: [{ path: '02-Work/Projects/IPP kickoff notes 1.md', detail: 'status: wip is not in the vocabulary for its type.' }],
  invalid_dates: [{ path: '02-Work/Tasks/Draft Phase 1 README run instructions.md', detail: 'due: next friday cannot be read as a date. The task is not carried into standups.' }],
})

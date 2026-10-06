import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { ToastProvider } from '@/components/Toast'
import { previewTimeline, previewUpskilling, previewWorkflowItems, type PreviewWorkflowItem } from '@/preview'
import { TimelinePage, UpskillingPage, WorkflowPage } from '.'
import { actionsFor, applyFilters, dailyCounts, stackedPaths } from './timeline'
import { weeklyCounts } from './upskilling'
import { applyAction, derive, validate } from './workflow'

const at = (ui: ReactElement, path = '/') =>
  render(
    <ToastProvider>
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </ToastProvider>,
  )

const { stageNames } = previewWorkflowItems
const item = (id: string): PreviewWorkflowItem => previewWorkflowItems.items.find((i) => i.id === id)!
const toastText = () =>
  screen
    .getAllByRole('status')
    .map((s) => s.textContent)
    .join(' ')

describe('workflow rules', () => {
  it('counts rework, detects the warning at two failures of one kind and a send-back', () => {
    const d = derive(item('retry'), stageNames)
    expect(d).toMatchObject({ rework: 2, sentBack: true, warned: true, stopped: false, previous: 'Testing', next: 'Testing' })
    expect(derive(item('dupes'), stageNames)).toMatchObject({ rework: 0, sentBack: false, next: 'N/A' })
  })
  it('stops at the third failure of one kind and sends the item to planning', () => {
    const { item: after, message } = applyAction(
      item('retry'),
      { mode: 'test', result: 'fail', cause: 'impl', note: 'again' },
      '2026-10-06',
      stageNames,
    )
    expect(derive(after, stageNames)).toMatchObject({ rework: 3, stopped: true })
    expect(after.stage).toBe(1)
    expect(message).toContain('02-Work/Tasks/Add retry with backoff to payment callback handler.md')
    expect(message).toContain('Third failure of the same kind')
  })
  it('a passed test moves the item to review', () => {
    const { item: after } = applyAction(item('retry'), { mode: 'test', result: 'pass', cause: '', note: '' }, '2026-10-06', stageNames)
    expect(after.stage).toBe(4)
  })
  it('a send-back must land behind the current stage', () => {
    expect(validate(item('reserve'), { mode: 'back', result: 'fail', cause: '', note: '' })).toMatch(/Pick the cause/)
    expect(validate(item('reserve'), { mode: 'back', result: 'fail', cause: 'impl', note: '' })).toMatch(/earlier stage/)
    expect(validate(item('n1'), { mode: 'back', result: 'fail', cause: 'impl', note: '' })).toBeNull()
  })
})

describe('WorkflowPage', () => {
  it('renders the banner, the six-stage strip with tags, the backward moves and every item', () => {
    at(<WorkflowPage />)
    expect(screen.getByText(/Phase 2\./)).toBeInTheDocument()
    expect(screen.getByText(/sample data/)).toBeInTheDocument()
    const strip = within(screen.getByRole('list', { name: 'Workflow stages' }))
    expect(strip.getAllByRole('listitem')).toHaveLength(6)
    expect(strip.getByText('Implementation').closest('li')).toHaveTextContent('3')
    expect(strip.getAllByText('1 blocked').length).toBeGreaterThan(0)
    expect(screen.getByText(/Backward moves/).parentElement).toHaveTextContent('Testing to Implementation')
    previewWorkflowItems.items.forEach((i) =>
      expect(screen.getByRole('button', { name: new RegExp(i.title.replace(/[+]/g, '\\+')) })).toBeInTheDocument(),
    )
    // Retry, reserve and the OTP expiry item were sent back.
    expect(screen.getAllByText('Sent back', { selector: 'span.font-semibold' })).toHaveLength(3)
  })

  it('filters by the project query parameter', async () => {
    const user = userEvent.setup()
    at(<WorkflowPage />, '/workflow?project=second-brain')
    expect(screen.getByRole('button', { name: /Verify templates in Obsidian/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Fix N\+1 query/ })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'All' }))
    expect(screen.getByRole('button', { name: /Fix N\+1 query/ })).toBeInTheDocument()
  })

  it('selecting an item shows its loop history, and the warning for two failures of one kind', async () => {
    const user = userEvent.setup()
    at(<WorkflowPage />)
    const panel = within(screen.getByRole('region', { name: 'Loop history of the selected item' }))
    expect(panel.getByText('Warning: two failures of the same kind')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Reserve wallet balance/ }))
    expect(panel.queryByText(/Warning: two failures/)).not.toBeInTheDocument()
    expect(panel.getByText('Review failed, design issue')).toBeInTheDocument()
    expect(panel.getByText(/PLAN_FAILURE/)).toBeInTheDocument()
  })

  it('records a third failure: the stop rule shows and the toast names the file', async () => {
    const user = userEvent.setup()
    at(<WorkflowPage />)
    await user.click(screen.getByRole('button', { name: 'Record test result' }))
    await user.click(screen.getByRole('button', { name: 'Failed' }))
    const submit = screen.getByRole('button', { name: 'Record result' })
    expect(submit).toBeDisabled()
    await user.selectOptions(screen.getByLabelText('Cause'), 'impl')
    await user.type(screen.getByLabelText('Note'), 'Third time')
    await user.click(submit)
    expect(toastText()).toContain('Updated 02-Work/Tasks/Add retry with backoff to payment callback handler.md: stage planning, rework 3')
    expect(screen.getByText('Stop rule reached')).toBeInTheDocument()
    expect(screen.queryByRole('form')).not.toBeInTheDocument()
  })

  it('disables the actions a stage does not allow and blocks a send-back that does not go back', async () => {
    const user = userEvent.setup()
    at(<WorkflowPage />)
    await user.click(screen.getByRole('button', { name: /Reserve wallet balance/ }))
    expect(screen.getByRole('button', { name: 'Record test result' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Record review result' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Send back' }))
    await user.selectOptions(screen.getByLabelText('Cause'), 'impl')
    expect(screen.getByRole('form', { name: 'Send back' })).toHaveTextContent(/earlier stage/)
    expect(screen.getAllByRole('button', { name: 'Send back' }).at(-1)).toBeDisabled()
  })
})

describe('timeline helpers', () => {
  it('filters by range, project, source and type from the as-of date', () => {
    const { events, asOf } = previewTimeline
    const base = { range: '7', project: 'all', source: 'all', type: 'all' }
    expect(applyFilters(events, { ...base, range: '1' }, asOf).every((e) => e.date === asOf)).toBe(true)
    expect(applyFilters(events, { ...base, source: 'jira' }, asOf).every((e) => e.source === 'jira')).toBe(true)
    expect(applyFilters(events, { ...base, project: 'second-brain' }, asOf).every((e) => e.projects.includes('second-brain'))).toBe(true)
    expect(applyFilters(events, { ...base, type: 'deploy' }, asOf)).toHaveLength(1)
  })
  it('counts every calendar day and builds one closed path per source', () => {
    const days = dailyCounts(previewTimeline.events, '7', previewTimeline.asOf)
    expect(days).toHaveLength(8)
    expect(days.at(-1)!.total).toBe(8)
    expect(days.find((d) => d.date === '2026-10-03')!.total).toBe(0)
    const paths = stackedPaths(days)
    expect(paths).toHaveLength(4)
    paths.forEach((p) => expect(p.d).toMatch(/^M .* Z$/))
  })
  it('offers actions by event type, each naming a file', () => {
    const ticket = previewTimeline.events.find((e) => e.id === 'a3')!
    expect(actionsFor(ticket).map((a) => a.label)).toContain('Start implementation')
    expect(actionsFor(ticket).find((a) => a.label === 'Create note')!.file).toBe('02-Work/Tickets/LUP-482.md')
  })
})

describe('TimelinePage', () => {
  it('renders the banner, four tiles, the chart with its numbers, the list and the trails', () => {
    at(<TimelinePage />)
    expect(screen.getByText(/Phase 4\./)).toBeInTheDocument()
    expect(screen.getByText('Tasks completed').closest('a')).toHaveTextContent('2')
    expect(screen.getByText('Deployments').closest('a')).toHaveAttribute('href', '/timeline?type=deploy')
    expect(screen.getByRole('img', { name: /Events per day: Sep 29 4/ })).toBeInTheDocument()
    expect(screen.getByText('How busy was each day?')).toBeInTheDocument()
    expect(screen.getByText(`Showing ${previewTimeline.events.length} of ${previewTimeline.events.length} events`)).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Tuesday 6 October' })).toBeInTheDocument()
    expect(screen.getByText('IPP-298')).toBeInTheDocument()
    expect(screen.getByText('Suggested link, not confirmed')).toBeInTheDocument()
  })

  it('filters through segmented controls and the type select, counts the result and resets', async () => {
    const user = userEvent.setup()
    at(<TimelinePage />)
    await user.click(screen.getByRole('button', { name: 'Today' }))
    expect(screen.getByText(`Showing 8 of ${previewTimeline.events.length} events`)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'GitLab' }))
    expect(screen.getByText(`Showing 3 of ${previewTimeline.events.length} events`)).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Type'), 'commit')
    expect(screen.getByText(`Showing 1 of ${previewTimeline.events.length} events`)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'IPP' }))
    await user.selectOptions(screen.getByLabelText('Type'), 'incident')
    expect(screen.getByText(/No events match these filters/)).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: 'Reset filters' })[0])
    expect(screen.getByText(`Showing ${previewTimeline.events.length} of ${previewTimeline.events.length} events`)).toBeInTheDocument()
  })

  it('reads the filters from the query parameters', () => {
    at(<TimelinePage />, '/timeline?type=deploy&range=7')
    expect(screen.getByText(`Showing 1 of ${previewTimeline.events.length} events`)).toBeInTheDocument()
    expect(screen.getByLabelText('Type')).toHaveValue('deploy')
  })

  it('selecting an event shows its detail and a context action names the file in a toast', async () => {
    const user = userEvent.setup()
    at(<TimelinePage />)
    const detail = within(screen.getByRole('region', { name: 'Selected event' }))
    expect(detail.getByText('LUP-482 OTP emails: relay log sample added to the ticket')).toBeInTheDocument()
    expect(detail.getByText(/Quoted from Jira/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Standup 2026-10-06/ }))
    expect(detail.getByRole('link', { name: '01-Daily/2026/2026-10-06.md' })).toBeInTheDocument()
    expect(detail.queryByRole('button', { name: 'Create task' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Clarify OTP expiry requirement/ }))
    await user.click(detail.getByRole('button', { name: 'Create follow-up' }))
    expect(toastText()).toContain('Would create 02-Work/Follow-ups/Follow up Clarify OTP expiry requirement.md')
  })

  it('links or dismisses the suggested trail on local state', async () => {
    const user = userEvent.setup()
    const first = at(<TimelinePage />)
    await user.click(screen.getByRole('button', { name: 'Link' }))
    expect(toastText()).toContain(
      'Would add [[Settlement file rerun review]] under Related in 02-Work/Tasks/Write runbook for settlement file rerun.md',
    )
    expect(screen.getByText('Linked.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Dismiss' })).not.toBeInTheDocument()
    first.unmount()
    at(<TimelinePage />)
    await user.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(toastText()).toContain('Dismissed. No file written.')
    expect(screen.getByText('Dismissed.')).toBeInTheDocument()
  })
})

describe('upskilling helpers', () => {
  it('counts notes per roadmap week up to the current week', () => {
    const counts = weeklyCounts(previewUpskilling.notes, previewUpskilling.roadmapStart, previewUpskilling.currentWeek)
    expect(counts.map((c) => c.total)).toEqual([2, 2, 2, 2, 3, 3])
    expect(counts[5]).toMatchObject({ learning: 1, practice: 1, applied: 1 })
  })
})

describe('UpskillingPage', () => {
  it('renders the banner, tiles, this week with its checklist, the 17-week strip and the lists', () => {
    at(<UpskillingPage />)
    expect(screen.getByText(/Phase 3\./)).toBeInTheDocument()
    expect(screen.getByText('Roadmap week').closest('a')).toHaveTextContent('6 of 17')
    expect(screen.getByText('Skill gaps from real work').closest('a')).toHaveTextContent('7')
    expect(screen.getByRole('heading', { name: 'Week 6: Idempotency and retries' })).toBeInTheDocument()
    expect(screen.getAllByRole('checkbox')).toHaveLength(5)
    expect(screen.getAllByRole('listitem', { name: /^Week \d+, / })).toHaveLength(17)
    expect(screen.getByRole('listitem', { name: /^Week 6, now/ })).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Notes per week' }).children).toHaveLength(6)
    expect(screen.getByText('Recently learned')).toBeInTheDocument()
    expect(screen.getByText(/Levels are words, not scores/)).toBeInTheDocument()
  })

  it('ticking a checklist item toasts the roadmap file and updates the count', async () => {
    const user = userEvent.setup()
    at(<UpskillingPage />)
    expect(screen.getByRole('heading', { name: /Week 6/ }).parentElement).toHaveTextContent('3 of 5 done')
    await user.click(screen.getByLabelText(/Classify callback failures before retrying, then/))
    expect(toastText()).toContain('Would update the checklist in 06-Upskilling/Roadmap/Week 06.md')
    expect(screen.getByRole('heading', { name: /Week 6/ }).parentElement).toHaveTextContent('4 of 5 done')
  })

  it('accepts, dismisses and undoes a recommendation on local state', async () => {
    const user = userEvent.setup()
    at(<UpskillingPage />)
    expect(screen.getAllByRole('button', { name: 'Accept' })).toHaveLength(3)
    const first = within(screen.getByRole('article', { name: 'Idempotency keys for payment callbacks' }))
    await user.click(first.getByRole('button', { name: 'Accept' }))
    expect(toastText()).toContain('Would add a next action to 06-Upskilling/Skills/Idempotency.md')
    expect(first.getByText('Accepted')).toBeInTheDocument()
    await user.click(first.getByRole('button', { name: 'Undo' }))
    expect(first.getByText('Suggested')).toBeInTheDocument()

    const second = within(screen.getByRole('article', { name: /Read the query plan/ }))
    await user.click(second.getByRole('button', { name: 'Dismiss' }))
    expect(toastText()).toContain('Would record the dismissal in 06-Upskilling/Skills/Query performance.md')
    expect(second.getByText('Dismissed')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Accept' })).toHaveLength(2)
  })

  it('selecting a skill shows its seven-step chain and the next missing step', async () => {
    const user = userEvent.setup()
    at(<UpskillingPage />)
    const chain = within(screen.getByRole('region', { name: 'Gap to lesson chain' }))
    expect(chain.getAllByRole('listitem')).toHaveLength(7)
    expect(chain.getByText(/Next: Applied to project has no note yet/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Query performance.*of 7 steps/ }))
    expect(chain.getByRole('heading', { name: 'Problem to lesson: Query performance' })).toBeInTheDocument()
    expect(chain.getByText(/Next: Review has no note yet/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Error contracts/ }))
    expect(chain.getAllByText('No note yet')).toHaveLength(7)
  })
})

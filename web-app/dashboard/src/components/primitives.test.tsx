import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderInApp } from '@/test/helpers'
import { task } from '@/test/notes'
import { buttonVariants } from '@/components/ui/button'
import { CardHead, CardRow } from './Card'
import { PreviewBadge } from './PreviewBadge'
import { PriorityMark } from './PriorityMark'
import { StatTile } from './StatTile'
import { StatusChip } from './StatusChip'
import { TaskRow } from './TaskRow'

describe('PriorityMark', () => {
  it.each([
    ['high', 'P1', 'High priority', 'font-bold'],
    ['medium', 'P2', 'Medium priority', 'font-medium'],
    ['low', 'P3', 'Low priority', 'font-normal'],
  ])('shows %s as %s, told apart by weight', (priority, mark, word, weight) => {
    renderInApp(<PriorityMark priority={priority} />)
    expect(screen.getByText(mark)).toBeInTheDocument()
    expect(screen.getByText(word)).toBeInTheDocument()
    expect(screen.getByText(mark).parentElement).toHaveClass(weight)
  })
  it('never uses a status colour', () => {
    const { container } = renderInApp(<PriorityMark priority="high" />)
    expect(container.innerHTML).not.toMatch(/status-|text-red|bg-tint/)
  })
  it('shows N/A for none or an unrecognised priority', () => {
    const { unmount } = renderInApp(<PriorityMark priority={null} />)
    expect(screen.getByText('N/A')).toBeInTheDocument()
    unmount()
    renderInApp(<PriorityMark priority="urgent" />)
    expect(screen.getByText('N/A')).toBeInTheDocument()
  })
})

describe('PreviewBadge', () => {
  it('is one labelled badge whose detail is available to keyboard and screen readers', async () => {
    const user = userEvent.setup()
    renderInApp(<PreviewBadge detail="From Calendar, Phase 4. Sample data" />)
    const badge = screen.getByText('Preview').closest('span')!
    expect(badge).toHaveTextContent('Preview: From Calendar, Phase 4. Sample data')
    await user.tab()
    expect(badge).toHaveFocus()
    expect((await screen.findAllByText('From Calendar, Phase 4. Sample data')).length).toBeGreaterThan(0)
  })
})

describe('StatusChip', () => {
  it('always shows the word, and tints only blocked', () => {
    const { unmount } = renderInApp(<StatusChip status="blocked" />)
    expect(screen.getByText('blocked')).toHaveClass('bg-tint-blocked')
    unmount()
    for (const status of ['planned', 'in-progress', 'review', 'done', 'cancelled']) {
      const view = renderInApp(<StatusChip status={status} />)
      expect(screen.getByText(status)).toBeInTheDocument()
      expect(screen.getByText(status).className).not.toMatch(/bg-tint/)
      expect(screen.getByText(status)).toHaveClass('bg-transparent')
      view.unmount()
    }
  })
  it('tints an overdue label given the blocked tone', () => {
    renderInApp(<StatusChip label="Overdue 3 days" tone="blocked" />)
    expect(screen.getByText('Overdue 3 days')).toHaveClass('bg-tint-blocked')
  })
  it('shows N/A for a missing status', () => {
    renderInApp(<StatusChip status={null} />)
    expect(screen.getByText('N/A')).toBeInTheDocument()
  })
})

describe('StatTile', () => {
  it('compact is 64px high and still a link to its list', () => {
    renderInApp(<StatTile compact icon="blocked" tone="blocked" value={2} label="Blocked" to="/tasks?status=blocked" />)
    const link = screen.getByRole('link')
    expect(link).toHaveClass('h-16')
    expect(link).toHaveAttribute('href', '/tasks?status=blocked')
    expect(link).toHaveTextContent('2Blocked')
  })
  it('the default variant is unchanged', () => {
    renderInApp(<StatTile icon="blocked" tone="blocked" value={2} label="Blocked" to="/tasks" />)
    expect(screen.getByRole('link')).not.toHaveClass('h-16')
  })
})

describe('Card density', () => {
  it('shows a count beside the panel title, not a subtitle, in a 40px header', () => {
    renderInApp(<CardHead title="Blocked" count={3} />)
    expect(screen.getByRole('heading', { name: 'Blocked' })).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('3').closest('div')!.parentElement).toHaveClass('min-h-10', 'px-3')
  })
  it('rows are 36px for one line and 48px for two', () => {
    renderInApp(
      <>
        <CardRow data-testid="one">a</CardRow>
        <CardRow data-testid="two" lines={2}>
          b
        </CardRow>
      </>,
    )
    expect(screen.getByTestId('one')).toHaveClass('min-h-9', 'px-3')
    expect(screen.getByTestId('two')).toHaveClass('min-h-12')
  })
})

describe('TaskRow', () => {
  const overdue = task('Rotate credentials', { priority: 'high', due: '2026-10-03', project: 'loadup' })
  it('is a 36px single line with priority, linked title, project and an overdue date that says so', () => {
    renderInApp(<TaskRow task={overdue} project="LoadUp" />)
    const row = screen.getByText('Rotate credentials').closest('div[class*="min-h"]')!
    expect(row).toHaveClass('min-h-9')
    expect(screen.getByText('P1')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Rotate credentials' })).toHaveAttribute('href', '/notes?path=02-Work%2FTasks%2FRotate%20credentials.md')
    expect(screen.getByText('LoadUp')).toBeInTheDocument()
    expect(screen.getByText('Overdue, Oct 3')).toHaveClass('text-status-blocked')
    expect(screen.getByText('planned')).toBeInTheDocument()
  })
  it('is a 48px two-line row when it has a reason, with the reason and project under the title', () => {
    renderInApp(<TaskRow task={overdue} project="LoadUp" reason="Overdue 3 days" />)
    expect(screen.getByText('Rotate credentials').closest('div[class*="min-h"]')).toHaveClass('min-h-12')
    expect(screen.getByText('Overdue 3 days · LoadUp')).toBeInTheDocument()
  })
  it('shows a due date that is not overdue as plain text, and N/A priority when none', () => {
    renderInApp(<TaskRow task={task('Later', { due: '2026-10-20' })} />)
    expect(screen.getByText('Due Oct 20')).not.toHaveClass('text-status-blocked')
    expect(screen.getByText('N/A')).toBeInTheDocument()
  })
  it('renders the status slot it is given', () => {
    renderInApp(<TaskRow task={overdue} status={<button>Custom status</button>} />)
    expect(screen.getByRole('button', { name: 'Custom status' })).toBeInTheDocument()
    expect(screen.queryByText('planned')).not.toBeInTheDocument()
  })
})

describe('type scale classes', () => {
  // Custom font-size utilities were once read by tailwind-merge as colours and deleted the text colour.
  it('keep both the size and the colour when merged', () => {
    expect(buttonVariants({ size: 'sm' })).toMatch(/t-small/)
    expect(buttonVariants({ size: 'sm' })).toMatch(/text-white/)
    expect(buttonVariants({ variant: 'secondary', size: 'sm' })).toMatch(/text-ink/)
    renderInApp(<PriorityMark priority="high" />)
    expect(screen.getByText('P1').parentElement).toHaveClass('t-caption', 'text-ink')
    renderInApp(<StatusChip status="done" />)
    expect(screen.getByText('done')).toHaveClass('t-caption', 'text-status-done')
  })
})

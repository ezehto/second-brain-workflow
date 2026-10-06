import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockClient, renderInApp, TODAY } from '@/test/helpers'
import { useProjectHref } from '@/lib/projectContext'
import { task } from '@/test/notes'
import { Button, buttonVariants } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import { TASK_SEGMENT_COLOR } from '@/domain/status'
import { StatusMenu } from './StatusMenu'
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
  const DETAIL = 'From Calendar, Phase 4. Sample data'
  it('is one labelled badge whose detail is available to keyboard and screen readers', async () => {
    const user = userEvent.setup()
    renderInApp(<PreviewBadge detail={DETAIL} />)
    const badge = screen.getByRole('button', { name: `Preview: ${DETAIL}` })
    await user.tab()
    expect(badge).toHaveFocus()
    expect((await screen.findAllByText(DETAIL)).length).toBeGreaterThan(0)
  })
  it('opens the detail on tap, where there is no hover or focus', async () => {
    const user = userEvent.setup()
    renderInApp(<PreviewBadge detail={DETAIL} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Preview/ }))
    expect(await screen.findByRole('dialog')).toHaveTextContent(DETAIL)
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
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

describe('project context on links', () => {
  it('a TaskRow link keeps the project of the page it is on', () => {
    renderInApp(<TaskRow task={task('Rotate credentials')} />, mockClient(), TODAY, '/tasks?project=ipp')
    expect(screen.getByRole('link', { name: 'Rotate credentials' }).getAttribute('href')).toBe('/notes?path=02-Work%2FTasks%2FRotate+credentials.md&project=ipp')
  })
  it('useProjectHref wraps note, project, tasks and plain links, and leaves them alone without a context', () => {
    function Probe() {
      const href = useProjectHref()
      return <p>{[href.note('a.md'), href.project('loadup'), href.tasks({ status: 'open' }), href.link('/index-status'), href.tasks({ project: 'gida' })].join(' | ')}</p>
    }
    const { unmount, container } = renderInApp(<Probe />, mockClient(), TODAY, '/tasks?project=ipp')
    expect(container.textContent).toBe('/notes?path=a.md&project=ipp | /projects/loadup?project=ipp | /tasks?status=open&project=ipp | /index-status?project=ipp | /tasks?project=gida')
    unmount()
    const plain = renderInApp(<Probe />)
    expect(plain.container.textContent).toBe('/notes?path=a.md | /projects/loadup | /tasks?status=open | /index-status | /tasks?project=gida')
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
  it('cn treats the scale names as font sizes: they replace a size and never a colour', () => {
    expect(cn('text-sm', 'text-caption')).toBe('text-caption')
    expect(cn('text-caption', 'text-sm')).toBe('text-sm')
    expect(cn('text-white', 'text-caption')).toBe('text-white text-caption')
    expect(cn('t-small', 'text-caption')).toBe('text-caption')
    expect(cn('text-caption', 'text-ink')).toBe('text-caption text-ink')
  })
  it('a text-caption override on a Button keeps the size classes and the text colour', () => {
    renderInApp(<Button size="sm" className="text-caption">Go</Button>)
    const button = screen.getByRole('button', { name: 'Go' })
    expect(button).toHaveClass('text-caption', 'h-8', 'px-2', 'text-white')
    expect(button).not.toHaveClass('t-small')
  })
  it('a text-caption override on a Label replaces its base size', () => {
    renderInApp(<Label className="text-caption">Name</Label>)
    const label = screen.getByText('Name')
    expect(label).toHaveClass('text-caption', 'font-medium')
    expect(label).not.toHaveClass('text-body')
  })
})

describe('segment colours', () => {
  // CSS is not loaded in tests, so the token value from index.css (--color-status-cancelled) is pinned here.
  it('the donut fill for inbox is the status-cancelled token', () => {
    expect(TASK_SEGMENT_COLOR.inbox).toBe('#8b8b9e')
  })
})

describe('editable row height', () => {
  it('a TaskRow with a StatusMenu stays a 36px row: the trigger gives back its padding', async () => {
    const note = task('Rotate credentials', { status: 'planned' })
    renderInApp(<TaskRow task={note} status={<StatusMenu note={note} />} />)
    const trigger = screen.getByRole('button', { name: /Change status/ })
    expect(trigger).toHaveClass('h-8', '-my-1', 'max-rail:min-h-11')
    expect(screen.getByText('Rotate credentials').closest('div[class*="min-h"]')).toHaveClass('min-h-9')
  })
})

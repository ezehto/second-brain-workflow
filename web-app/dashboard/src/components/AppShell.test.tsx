import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderApp } from '@/test/helpers'
import { setViewport } from '@/test/viewport'

const main = () => screen.findByRole('navigation', { name: 'Main' })

describe('navigation by width', () => {
  it('1280 and up: a labelled rail with groups, counts and the sample-data note', async () => {
    renderApp()
    const nav = await main()
    expect(within(nav).getByText('Second Brain')).toBeInTheDocument()
    for (const group of ['Today', 'Work', 'Knowledge', 'System']) expect(within(nav).getAllByText(group).length).toBeGreaterThan(0)
    expect(within(nav).getAllByRole('link').map((l) => l.textContent?.replace(/Count: \d+/, ''))).toEqual([
      'Today',
      'Standup',
      'Inbox',
      'Tasks',
      'Projects',
      'Knowledge',
      'Decisions',
      'Search',
      'Index status',
    ])
    expect(within(nav).getByText(/Sample data/)).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Primary' })).not.toBeInTheDocument()
  })

  it('shows counts on Inbox, Tasks (blocked) and Index status', async () => {
    renderApp()
    const nav = await main()
    expect(await within(nav).findByRole('link', { name: /Inbox/ })).toHaveTextContent('Count: 4')
    expect(within(nav).getByRole('link', { name: /Tasks/ })).toHaveTextContent('Count: 2')
    expect(within(nav).getByRole('link', { name: /Index status/ })).toHaveTextContent('Count: 8')
    expect(within(nav).getByRole('link', { name: 'Standup' })).not.toHaveTextContent('Count')
  })

  it('832 to 1279: a 72px icon rail whose items are named and have tooltips', async () => {
    setViewport(1024)
    const user = userEvent.setup()
    renderApp()
    const nav = await main()
    expect(within(nav).queryByText('Second Brain')).not.toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: 'Standup' })).toBeInTheDocument()
    expect(within(nav).queryByText('Standup')).not.toBeInTheDocument()
    await user.hover(within(nav).getByRole('link', { name: 'Standup' }))
    expect((await screen.findAllByText('Standup')).length).toBeGreaterThan(0)
    expect(nav.closest('aside')).toHaveClass('w-[4.5rem]')
    expect(within(nav).getByRole('link', { name: 'Today' })).toHaveClass('bg-brand-fill')
    expect(within(nav).getByRole('link', { name: /Inbox/ })).toHaveTextContent('Count: 4')
  })

  it('640 to 831: no rail, a menu button, and a bottom tab bar', async () => {
    setViewport(700)
    const user = userEvent.setup()
    renderApp()
    const tabs = await screen.findByRole('navigation', { name: 'Primary' })
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
    expect(within(tabs).getAllByRole('link').map((l) => l.textContent?.replace(/Count: \d+/, ''))).toEqual(['Today', 'Tasks', 'Standup', 'Projects'])
    expect(screen.queryByRole('button', { name: 'Capture' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Open navigation' }))
    const sheet = await screen.findByRole('dialog', { name: 'Navigation' })
    expect(within(sheet).getByRole('link', { name: /Tasks/ })).toBeInTheDocument()
    expect(within(sheet).getByRole('combobox', { name: 'Project' })).toBeInTheDocument()
  })

  it('under 640: 48px top bar, bottom tab bar with More, and no floating capture button', async () => {
    setViewport(390)
    const user = userEvent.setup()
    renderApp()
    const tabs = await screen.findByRole('navigation', { name: 'Primary' })
    expect(screen.getByRole('banner')).toHaveClass('h-12')
    expect(within(tabs).getAllByRole('link')).toHaveLength(4)
    expect(screen.getByRole('link', { name: 'Search' })).toBeInTheDocument()
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Capture' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'New' })).toBeInTheDocument()
    await user.click(within(tabs).getByRole('button', { name: 'More' }))
    const sheet = await screen.findByRole('dialog', { name: 'More' })
    // The sheet holds what the tab bar does not, and the context select.
    expect(within(sheet).getByRole('link', { name: /Inbox/ })).toBeInTheDocument()
    expect(within(sheet).getByRole('link', { name: /Index status/ })).toBeInTheDocument()
    expect(within(sheet).queryByRole('link', { name: /Tasks/ })).not.toBeInTheDocument()
    expect(within(sheet).getByRole('combobox', { name: 'Project' })).toBeInTheDocument()
  })

  it('on a phone, captures through the header New button', async () => {
    setViewport(390)
    const user = userEvent.setup()
    renderApp()
    await user.click(await screen.findByRole('button', { name: 'New' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Capture' }))
    expect(await screen.findByRole('dialog', { name: 'Capture' })).toBeInTheDocument()
  })

  it('follows a resize between layouts', async () => {
    renderApp()
    await main()
    setViewport(500)
    expect(await screen.findByRole('navigation', { name: 'Primary' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
  })
})

describe('the Later group', () => {
  it('is collapsed, opens on demand, and remembers it', async () => {
    const user = userEvent.setup()
    const first = renderApp()
    const nav = await main()
    expect(within(nav).queryByRole('link', { name: 'Workflow' })).not.toBeInTheDocument()
    const toggle = within(nav).getByRole('button', { name: /Later/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(toggle).not.toHaveAttribute('aria-controls')
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-controls')
    expect(within(nav).getAllByRole('link').map((l) => l.textContent)).toEqual(expect.arrayContaining(['Workflow', 'Timeline', 'Upskilling']))
    expect(window.localStorage.getItem('sb.rail.later')).toBe('1')
    first.unmount()
    renderApp()
    expect(await within(await main()).findByRole('link', { name: 'Workflow' })).toBeInTheDocument()
    await user.click(within(await main()).getByRole('button', { name: /Later/ }))
    expect(within(await main()).queryByRole('link', { name: 'Workflow' })).not.toBeInTheDocument()
    expect(window.localStorage.getItem('sb.rail.later')).toBe('0')
  })

  it('is open while the current page is one of its items', async () => {
    renderApp('/workflow')
    expect(await within(await main()).findByRole('link', { name: 'Workflow' })).toBeInTheDocument()
  })

  it('works when storage is blocked', async () => {
    const original = Storage.prototype.setItem
    Storage.prototype.setItem = () => {
      throw new Error('blocked')
    }
    try {
      const user = userEvent.setup()
      renderApp()
      await user.click(within(await main()).getByRole('button', { name: /Later/ }))
      expect(within(await main()).getByRole('link', { name: 'Workflow' })).toBeInTheDocument()
    } finally {
      Storage.prototype.setItem = original
    }
  })
})

describe('project context', () => {
  it('is carried by every navigation link', async () => {
    renderApp('/?project=ipp')
    const nav = await main()
    expect(within(nav).getByRole('link', { name: 'Standup' })).toHaveAttribute('href', '/standups?project=ipp')
    expect(within(nav).getByRole('link', { name: /Tasks/ })).toHaveAttribute('href', '/tasks?project=ipp')
    expect(within(nav).getByRole('link', { name: 'Today' })).toHaveAttribute('href', '/?project=ipp')
  })

  it('has no parameter by default', async () => {
    renderApp()
    expect(within(await main()).getByRole('link', { name: /Tasks/ })).toHaveAttribute('href', '/tasks')
  })

  it('is written by the context select without disturbing other parameters, and removed by All projects', async () => {
    const user = userEvent.setup()
    renderApp('/inbox?status=blocked')
    const nav = await main()
    await user.click(await screen.findByRole('combobox', { name: 'Project' }))
    await user.click(await screen.findByRole('option', { name: 'IPP' }))
    expect(within(nav).getByRole('link', { name: 'Projects' })).toHaveAttribute('href', '/projects?project=ipp')
    await user.click(screen.getByRole('combobox', { name: 'Project' }))
    await user.click(await screen.findByRole('option', { name: 'All projects' }))
    expect(within(nav).getByRole('link', { name: 'Projects' })).toHaveAttribute('href', '/projects')
  })

  it('shows a project from the URL even if it is not active', async () => {
    renderApp('/?project=monitoring-dashboard')
    expect(await screen.findByRole('combobox', { name: 'Project' })).toHaveTextContent('monitoring-dashboard')
  })
})

describe('top bar', () => {
  it('shows the date as the title on Today, with the route subtitle, and no Start standup', async () => {
    renderApp()
    expect(await screen.findByRole('heading', { level: 1, name: 'Tuesday 6 October' })).toBeInTheDocument()
    expect(screen.getByText(/Read from your vault at 14:39/)).toBeInTheDocument()
    expect(within(screen.getByRole('banner')).queryByText('Start standup')).not.toBeInTheDocument()
    expect(document.title).toBe('Today · Second Brain')
  })

  it('shows the page title for other routes, and uses it for the tab', async () => {
    renderApp('/tasks')
    expect(await screen.findByRole('heading', { level: 1, name: 'Tasks' })).toBeInTheDocument()
    expect(document.title).toBe('Tasks · Second Brain')
  })

  it('shows the project name as the title on a project page, and falls back to the route title elsewhere', async () => {
    renderApp('/projects/ipp')
    expect(await screen.findByRole('heading', { level: 1, name: 'IPP' })).toBeInTheDocument()
    expect(document.title).toBe('IPP · Second Brain')
  })

  it('shows the note title as the title on the note page', async () => {
    renderApp(`/notes?path=${encodeURIComponent('02-Work/Tasks/Investigate missing OTP email.md')}`)
    expect(await screen.findByRole('heading', { level: 1, name: 'Investigate missing OTP email' })).toBeInTheDocument()
  })

  it('shows the index badge for errors only, while the rail keeps the total of problems', async () => {
    renderApp()
    expect(await screen.findByRole('link', { name: /2 index errors/ })).toHaveAttribute('href', '/index-status')
    expect(within(screen.getByRole('navigation', { name: 'Main' })).getByRole('link', { name: /Index status/ })).toHaveTextContent('8')
  })

  it('Ctrl+K opens the command palette, and the hint is shown', async () => {
    const user = userEvent.setup()
    renderApp()
    await screen.findByRole('searchbox', { name: 'Search the vault' })
    expect(screen.queryByRole('dialog', { name: 'Command palette' })).not.toBeInTheDocument()
    await user.keyboard('{Control>}k{/Control}')
    expect(await screen.findByRole('dialog', { name: 'Command palette' })).toBeInTheDocument()
    expect(screen.getByText('Ctrl K')).toBeInTheDocument()
  })

  it('searches on Enter and keeps the project context', async () => {
    const user = userEvent.setup()
    renderApp('/?project=ipp')
    await user.type(await screen.findByRole('searchbox'), 'otp{Enter}')
    expect(await screen.findByRole('heading', { level: 1, name: 'Search' })).toBeInTheDocument()
    expect(within(await main()).getByRole('link', { name: 'Search' })).toHaveAttribute('href', '/search?project=ipp')
  })

  it('shows the user from me()', async () => {
    renderApp()
    expect(await screen.findByText('Signed in as raymark')).toBeInTheDocument()
  })
})

describe('New menu', () => {
  it.each([
    ['Task', 'Create task'],
    ['Follow-up', 'Add follow-up'],
    ['Decision', 'Record decision'],
    ['Note', 'Add note'],
    ['Capture', 'Capture'],
  ])('opens the %s dialog', async (item, dialog) => {
    const user = userEvent.setup()
    renderApp()
    await user.click(await screen.findByRole('button', { name: 'New' }))
    await user.click(await screen.findByRole('menuitem', { name: item }))
    expect(await screen.findByRole('dialog', { name: dialog })).toBeInTheDocument()
  })

  it('is opened by the keyboard and shows the shortcuts', async () => {
    const user = userEvent.setup()
    renderApp()
    const button = await screen.findByRole('button', { name: 'New' })
    button.focus()
    await user.keyboard('{Enter}')
    expect((await screen.findAllByRole('menuitem')).map((i) => i.textContent)).toEqual(['TaskT', 'Follow-upF', 'DecisionD', 'NoteN', 'CaptureC'])
  })
})

describe('content area', () => {
  it('is at most 1840px wide with a 24px gutter (16px on a phone)', async () => {
    renderApp()
    const area = (await screen.findByRole('main')) as HTMLElement
    expect(area).toHaveClass('max-w-[1840px]', 'px-4', 'sm:px-6', 'mx-auto')
  })
})

describe('the menu on a resize', () => {
  it('starts closed again when the layout changes', async () => {
    setViewport(700)
    const user = userEvent.setup()
    renderApp()
    await screen.findByRole('navigation', { name: 'Primary' })
    await user.click(screen.getByRole('button', { name: 'Open navigation' }))
    expect(screen.getByRole('dialog', { name: 'Navigation' })).toBeInTheDocument()
    setViewport(1024)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    setViewport(700)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

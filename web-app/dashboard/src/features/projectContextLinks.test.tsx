import { configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderRoutes } from '@/features/notes/testing'
import { InboxPage } from '@/features/inbox'
import { renderApp } from '@/test/helpers'

configure({ asyncUtilTimeout: 5000 })

/** Every internal link in the page body must keep the project context. */
async function expectContextOnLinks(url: string, ready: () => Promise<unknown>) {
  renderApp(url)
  await ready()
  const main = screen.getByRole('main')
  const internal = within(main)
    .getAllByRole('link')
    .map((a) => a.getAttribute('href')!)
    .filter((h) => h.startsWith('/'))
  expect(internal.length).toBeGreaterThan(0)
  for (const h of internal) expect(h, h).toContain('project=ipp')
}

describe('the project context on in-page links', () => {
  it('Dashboard', () => expectContextOnLinks('/?project=ipp', () => screen.findByRole('region', { name: 'Focus' })))
  it('Projects', () => expectContextOnLinks('/projects?project=ipp', () => screen.findByRole('link', { name: 'IPP' })))
  it('Project', () => expectContextOnLinks('/projects/ipp?project=ipp', () => screen.findByRole('heading', { name: 'Next tasks' })))
  it('Knowledge', () => expectContextOnLinks('/knowledge?project=ipp', () => screen.findAllByRole('link', { name: /idempotent|retry|OTP|replay|log/i })))
  it('Decisions', () => expectContextOnLinks('/decisions?project=ipp', () => screen.findAllByRole('link', { name: /idempotency/i })))
  it('Index status', () => expectContextOnLinks('/index-status?project=ipp', () => screen.findByRole('heading', { name: /Problems|problems/ })))

  it('Inbox opens a note on a narrow screen with the project kept', async () => {
    const user = userEvent.setup()
    const { router } = renderRoutes(
      [
        { path: '/inbox', element: <InboxPage /> },
        { path: '/notes', element: <p>reader</p> },
      ],
      '/inbox?project=ipp',
      undefined,
      700,
    )
    await user.click((await screen.findAllByRole('button', { name: /^Open / }))[0])
    await waitFor(() => expect(router.state.location.pathname).toBe('/notes'))
    expect(new URLSearchParams(router.state.location.search).get('project')).toBe('ipp')
  })
})


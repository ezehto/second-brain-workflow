import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockClient, renderApp } from '@/test/helpers'

describe('App', () => {
  it('renders the shell and the dashboard from the mock API', async () => {
    renderApp()
    expect(await screen.findByRole('heading', { level: 1, name: 'Tuesday 6 October' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: "Today's focus" })).toBeInTheDocument()
    expect((await screen.findAllByText('Rotate staging API credentials')).length).toBeGreaterThan(0)
  })

  it('shows the Not built yet page inside the shell for a page that is not built', async () => {
    renderApp('/tasks')
    expect(await screen.findByRole('heading', { level: 1, name: 'Tasks' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Not built yet' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
  })

  it("uses the server's date, not the browser's, when they differ", async () => {
    // The backend test clock (plan 2.12) pins the vault to a day the browser does not share.
    renderApp('/', mockClient({ today: '2026-10-09' }), '2026-10-06')
    expect(await screen.findByRole('heading', { level: 1, name: 'Friday 9 October' })).toBeInTheDocument()
    expect(screen.getByText('01-Daily/2026/2026-10-09.md')).toBeInTheDocument()
  })

  describe('when the dashboard query fails', () => {
    const failingOnce = () => {
      const client = mockClient()
      const getDashboard = client.getDashboard
      let calls = 0
      client.getDashboard = () => (++calls === 1 ? Promise.reject(new Error('Dashboard is down')) : getDashboard())
      return client
    }

    it('still renders another route inside the shell', async () => {
      renderApp('/tasks', failingOnce())
      expect(await screen.findByRole('heading', { name: 'Not built yet' })).toBeInTheDocument()
      expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
    })

    it('shows the error state on the Dashboard, and a retry recovers it', async () => {
      const user = userEvent.setup()
      renderApp('/', failingOnce())
      const alerts = await screen.findAllByRole('alert')
      expect(alerts[0]).toHaveTextContent('Dashboard is down')
      await user.click(screen.getAllByRole('button', { name: 'Try again' })[0])
      expect(await screen.findByRole('heading', { level: 1, name: 'Tuesday 6 October' })).toBeInTheDocument()
      expect(await screen.findByText('Not started')).toBeInTheDocument()
    })
  })
})

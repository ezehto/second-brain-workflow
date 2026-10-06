import { act, configure, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { App } from '@/App'
import { ApiError, type ApiClient } from '@/api/client'
import { fixedClock } from '@/lib/clock'
import { createRoutes } from '@/routes'
import { mockClient, TODAY } from '@/test/helpers'
import { safeNext } from './next'

configure({ asyncUtilTimeout: 5000 })

/** The whole app at `path` on the mock API, with the session endpoints under the test's control. */
function openApp(path: string, overrides: Partial<ApiClient> = {}) {
  const listeners = new Set<() => void>()
  const client: ApiClient = {
    ...mockClient(),
    onUnauthenticated: (listener) => {
      listeners.add(listener)
      return () => void listeners.delete(listener)
    },
    ...overrides,
  }
  const router = createMemoryRouter(createRoutes({ sampleData: true }), { initialEntries: [path] })
  render(<App client={client} clock={fixedClock(TODAY)} router={router} />)
  const location = () => `${router.state.location.pathname}${router.state.location.search}`
  return { client, router, location, sessionLost: () => act(() => listeners.forEach((l) => l())) }
}

const signedOut = () => Promise.reject(new ApiError(403, 'Authentication credentials were not provided.'))

async function signIn(user: ReturnType<typeof userEvent.setup>, username = 'raymark', password = 'a-password') {
  await user.type(await screen.findByLabelText('Username'), username)
  await user.type(screen.getByLabelText('Password'), password)
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
}

describe('redirect to login and back', () => {
  it('sends a signed-out visitor to /login with ?next=, and back there after signing in', async () => {
    const user = userEvent.setup()
    const app = openApp('/tasks?status=blocked', { me: signedOut })
    expect(await screen.findByRole('heading', { level: 1, name: 'Second Brain' })).toBeInTheDocument()
    expect(app.location()).toBe(`/login?next=${encodeURIComponent('/tasks?status=blocked')}`)

    await signIn(user)
    await waitFor(() => expect(app.location()).toBe('/tasks?status=blocked'))
    expect(await screen.findByRole('heading', { level: 1, name: 'Tasks' })).toBeInTheDocument()
  })

  it('goes to the dashboard after signing in when there was no next', async () => {
    const user = userEvent.setup()
    const app = openApp('/', { me: signedOut })
    await signIn(user)
    await waitFor(() => expect(app.location()).toBe('/'))
    expect(await screen.findByRole('heading', { level: 1, name: 'Tuesday 6 October' })).toBeInTheDocument()
  })

  it('redirects mid-session when the session-lost listener fires directly (what a 401 or 403 does)', async () => {
    const app = openApp('/inbox')
    expect(await screen.findByRole('heading', { level: 1, name: 'Inbox' })).toBeInTheDocument()
    app.sessionLost()
    expect(await screen.findByLabelText('Username')).toBeInTheDocument()
    expect(app.location()).toBe(`/login?next=${encodeURIComponent('/inbox')}`)
  })

  it('does not show the shell or request data while signed out', async () => {
    const getDashboard = vi.fn(() => new Promise<never>(() => {}))
    openApp('/', { me: signedOut, getDashboard })
    await screen.findByLabelText('Username')
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
    expect(getDashboard).not.toHaveBeenCalled()
  })

  it('sends a signed-in visitor on from /login', async () => {
    const app = openApp('/login?next=%2Fprojects')
    expect(await screen.findByRole('heading', { level: 1, name: 'Projects' })).toBeInTheDocument()
    expect(app.location()).toBe('/projects')
  })

  it('shows a retry, not the login page, when the server cannot be reached', async () => {
    const me = vi.fn().mockRejectedValueOnce(new ApiError(0, 'Cannot reach the server.')).mockResolvedValue({ username: 'raymark' })
    const user = userEvent.setup()
    openApp('/', { me })
    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach the server.')
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Tuesday 6 October' })).toBeInTheDocument()
  })
})

describe('safeNext', () => {
  it.each([
    ['/tasks?status=done', '/tasks?status=done'],
    ['/notes?path=a%2Fb.md', '/notes?path=a%2Fb.md'],
    [null, '/'],
    ['', '/'],
    ['https://evil.example/', '/'],
    ['//evil.example', '/'],
    ['/\\evil.example', '/'],
    ['/\t/evil.example', '/'],
    ['/\n/evil.example', '/'],
    ['/tasks\nx', '/'],
    ['javascript:alert(1)', '/'],
    ['tasks', '/'],
    ['/login', '/'],
    ['/login?next=%2Ftasks', '/'],
  ])('%s becomes %s', (input, expected) => {
    expect(safeNext(input)).toBe(expected)
  })
})

describe('the login page', () => {
  it('shows the API message and clears the password when the credentials are wrong', async () => {
    const user = userEvent.setup()
    const login = vi.fn().mockRejectedValue(new ApiError(400, 'Invalid username or password.'))
    openApp('/login', { me: signedOut, login })
    await signIn(user, 'raymark', 'wrong')
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password.')
    expect(login).toHaveBeenCalledWith({ username: 'raymark', password: 'wrong' })
    expect(screen.getByLabelText('Password')).toHaveValue('')
    expect(screen.getByLabelText('Username')).toHaveValue('raymark')
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled()
  })

  it('shows the throttle message on 429 and a CSRF failure as the API words it', async () => {
    const user = userEvent.setup()
    const login = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(429, 'Too many attempts. Wait a minute, then try again.'))
      .mockRejectedValueOnce(new ApiError(403, 'CSRF failed.'))
    openApp('/login', { me: signedOut, login })
    await signIn(user)
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many attempts')
    await user.type(screen.getByLabelText('Password'), 'again')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('CSRF failed.'))
  })

  it('asks for both fields without calling the API', async () => {
    const user = userEvent.setup()
    const login = vi.fn()
    openApp('/login', { me: signedOut, login })
    await user.click(await screen.findByRole('button', { name: 'Sign in' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter your username and password.')
    expect(login).not.toHaveBeenCalled()
  })

  it('uses standard autocomplete values and a password field', async () => {
    openApp('/login', { me: signedOut })
    expect(await screen.findByLabelText('Username')).toHaveAttribute('autocomplete', 'username')
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password')
    expect(screen.getByLabelText('Password')).toHaveAttribute('autocomplete', 'current-password')
  })
})

describe('sign out', () => {
  it('calls logout, clears the session and shows the login page without a next', async () => {
    const user = userEvent.setup()
    const logout = vi.fn().mockResolvedValue(undefined)
    const app = openApp('/tasks', { logout })
    await user.click(await screen.findByRole('button', { name: 'Signed in as raymark' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Sign out' }))
    expect(logout).toHaveBeenCalledTimes(1)
    expect(await screen.findByLabelText('Username')).toBeInTheDocument()
    expect(app.location()).toBe('/login')
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
  })

  it('still signs this browser out when the server call fails', async () => {
    const user = userEvent.setup()
    const logout = vi.fn().mockRejectedValue(new ApiError(0, 'Cannot reach the server.'))
    const app = openApp('/', { logout })
    await user.click(await screen.findByRole('button', { name: 'Signed in as raymark' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Sign out' }))
    expect(await screen.findByLabelText('Username')).toBeInTheDocument()
    expect(app.location()).toBe('/login')
  })
})

import { useEffect, useState, type FormEvent } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { safeNext } from './next'
import { useSession } from './SessionProvider'

/**
 * The one page outside the shell: a single card on the page ground. The API's own message is
 * shown for a failure ("Invalid username or password." is deliberately the same for both
 * fields), and a signed-in visitor is sent straight on.
 */
export function LoginPage() {
  const { state, login } = useSession()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    document.title = 'Sign in · Second Brain'
  }, [])

  if (state.status === 'authenticated' && !busy) return <Navigate to={next} replace />

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    if (!username.trim() || !password) {
      setError('Enter your username and password.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await login(username.trim(), password)
      navigate(next, { replace: true })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not sign in. Try again.')
      setPassword('')
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-ground px-4 py-10">
      <form
        onSubmit={onSubmit}
        noValidate
        aria-labelledby="login-title"
        className="flex w-full max-w-sm flex-col gap-4 rounded-card border border-line bg-surface p-6"
      >
        <div className="flex flex-col gap-1">
          <h1 id="login-title" className="page-title m-0">
            Second Brain
          </h1>
          <p className="t-small m-0 text-muted-ink">Sign in to read and update your vault.</p>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="login-username">Username</Label>
          <Input
            id="login-username"
            name="username"
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? 'login-error' : undefined}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="login-password">Password</Label>
          <Input
            id="login-password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? 'login-error' : undefined}
          />
        </div>

        {error && (
          <p id="login-error" role="alert" className="t-small m-0 font-medium text-status-blocked">
            {error}
          </p>
        )}

        <Button type="submit" disabled={busy} className="w-full max-rail:min-h-11">
          {busy ? 'Signing in' : 'Sign in'}
        </Button>
      </form>
    </main>
  )
}

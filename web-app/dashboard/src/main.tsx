import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter } from 'react-router'
import './index.css'
import { App } from './App'
import { createApiClient, resolveApiMode } from './api/ApiProvider'
import { readCsrfCookie } from './api/http'
import { FIXTURE_TODAY } from './api/mock/fixtures'
import { fixedClock, systemClock } from './lib/clock'
import { createRoutes } from './routes'

const mode = resolveApiMode(import.meta.env.VITE_API_MODE)
// The mock data is written for one day: the mock API and the clock both take it
// from this one value. In http mode the shell asks the server for the date and
// the system clock is only the fallback.
const mockToday = FIXTURE_TODAY
const clock = mode === 'mock' ? fixedClock(mockToday) : systemClock
const router = createBrowserRouter(createRoutes({ sampleData: mode === 'mock' }))

const client = createApiClient(mode, { today: mockToday })
// Login is a POST: have the CSRF cookie before the person can submit it.
if (mode === 'http' && !readCsrfCookie()) client.csrf().catch(() => undefined)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App client={client} clock={clock} router={router} />
  </StrictMode>,
)

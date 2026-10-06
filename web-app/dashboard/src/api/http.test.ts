import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './client'
import schema from './generated/schema.d.ts?raw'
import { createHttpClient, readCsrfCookie } from './http'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const empty = (status = 204) => new Response(null, { status })

function setup(...responses: Response[]) {
  const queue = [...responses]
  const fetchMock = vi.fn<typeof fetch>(async () => queue.shift() ?? empty())
  return { client: createHttpClient({ fetch: fetchMock }), fetchMock }
}
const call = (fetchMock: ReturnType<typeof setup>['fetchMock'], n = 0) => {
  const [url, init] = fetchMock.mock.calls[n]
  const headers = (init?.headers ?? {}) as Record<string, string>
  return { url: String(url), method: init?.method, headers, body: init?.body, credentials: init?.credentials }
}
const setCookie = (value: string | null) => {
  document.cookie = `csrftoken=${value ?? ''}; path=/${value === null ? '; max-age=0' : ''}`
}

beforeEach(() => setCookie(null))
afterEach(() => setCookie(null))

describe('CSRF', () => {
  it('reads the csrftoken cookie, decoded', () => {
    expect(readCsrfCookie()).toBeNull()
    setCookie('a%2Fb')
    expect(readCsrfCookie()).toBe('a/b')
  })

  it('sends X-CSRFToken from the cookie on every unsafe method', async () => {
    setCookie('tok123')
    const { client, fetchMock } = setup(json({ username: 'u' }), empty(), json({}, 201), json({}), json({}, 201))
    await client.login({ username: 'u', password: 'p' })
    await client.logout()
    await client.createNote({ type: 'task', title: 'T' })
    await client.changeStatus({ path: 'a.md', status: 'done', expected_hash: 'h' })
    await client.startStandup()
    for (let i = 0; i < 5; i++) {
      expect(call(fetchMock, i).method).toBe('POST')
      expect(call(fetchMock, i).headers['X-CSRFToken']).toBe('tok123')
    }
  })

  it('never sends it on a GET, even when the cookie exists', async () => {
    setCookie('tok123')
    const { client, fetchMock } = setup(json({ username: 'u' }), json({ count: 0, next: null, previous: null, results: [] }), json({}), empty())
    await client.me()
    await client.listNotes()
    await client.getDashboard()
    await client.csrf()
    for (let i = 0; i < 4; i++) {
      expect(call(fetchMock, i).method).toBe('GET')
      expect(call(fetchMock, i).headers).not.toHaveProperty('X-CSRFToken')
    }
  })

  it('reads the cookie at the time of each request (Django rotates it at login)', async () => {
    setCookie('before')
    const { client, fetchMock } = setup(json({ username: 'u' }), empty())
    await client.login({ username: 'u', password: 'p' })
    setCookie('after')
    await client.logout()
    expect(call(fetchMock, 0).headers['X-CSRFToken']).toBe('before')
    expect(call(fetchMock, 1).headers['X-CSRFToken']).toBe('after')
  })

  it('asks GET /api/auth/csrf/ first when the cookie is missing, then sends the token it set', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      if (String(input) === '/api/auth/csrf/') {
        setCookie('fresh')
        return empty()
      }
      return json({ username: 'u' })
    })
    await createHttpClient({ fetch: fetchMock }).login({ username: 'u', password: 'p' })
    expect(call(fetchMock, 0)).toMatchObject({ url: '/api/auth/csrf/', method: 'GET' })
    expect(call(fetchMock, 1)).toMatchObject({ url: '/api/auth/login/', method: 'POST' })
    expect(call(fetchMock, 1).headers['X-CSRFToken']).toBe('fresh')
  })

  it('sends cookies same-origin and JSON for a body', async () => {
    setCookie('t')
    const { client, fetchMock } = setup(json({ username: 'u' }))
    await client.login({ username: 'u', password: 'p' })
    const sent = call(fetchMock)
    expect(sent.credentials).toBe('same-origin')
    expect(sent.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(String(sent.body))).toEqual({ username: 'u', password: 'p' })
  })
})

describe('requests', () => {
  it('every method calls a path that exists in the contract', async () => {
    setCookie('t')
    const page = { count: 0, next: null, previous: null, results: [] }
    const { client, fetchMock } = setup(
      empty(), json({ username: 'u' }), empty(), json({ username: 'u' }), json({ status: 'ok' }),
      json(page), json({}), json({}, 201), json({}),
      json({}, 201), json({}),
      json([]), json({}),
      json({ exists: true }), json({}, 201), json({}),
      json({}), json({ query: 'q', results: [] }), json({}), json({}), json({}),
    )
    await client.csrf()
    await client.login({ username: 'u', password: 'p' })
    await client.logout()
    await client.me()
    await client.health()
    await client.listNotes()
    await client.lookupNote({ path: 'a.md' })
    await client.createNote({ type: 'task', title: 'T' })
    await client.changeStatus({ path: 'a.md', status: 'done', expected_hash: 'h' })
    await client.createCapture({ text: 'x' })
    await client.triageCapture({ path: 'a.md', expected_hash: 'h', action: 'keep' })
    await client.listProjects()
    await client.getProject('alpha')
    await client.getStandupToday()
    await client.startStandup()
    await client.appendToStandup({ section: 'Done', text: 'x', expected_hash: 'h' })
    await client.getDashboard()
    await client.search('q')
    await client.getIndexStatus()
    await client.refreshIndex()
    const seen = new Set<string>()
    for (let i = 0; i < fetchMock.mock.calls.length; i++) {
      const { url } = call(fetchMock, i)
      const path = url.split('?')[0].replace('/projects/alpha/', '/projects/{slug}/')
      seen.add(path)
      expect(schema, path).toContain(`"${path}": {`)
    }
    // 18 distinct paths: every operation of the contract but the schema document itself.
    expect(seen.size).toBe(18)
  })

  it('repeats status and drops undefined params in the notes query', async () => {
    const { client, fetchMock } = setup(json({ count: 0, results: [] }))
    const page = await client.listNotes({ type: 'task', status: ['planned', 'blocked'], overdue: true, page: 2, project: undefined })
    expect(call(fetchMock).url).toBe('/api/notes/?type=task&status=planned&status=blocked&overdue=true&page=2')
    expect(page).toEqual({ count: 0, next: null, previous: null, results: [] })
  })

  it('looks a note up by path or id, and encodes a project slug', async () => {
    const { client, fetchMock } = setup(json({}), json({}), json({}))
    await client.lookupNote({ path: '02-Work/A b.md' })
    await client.lookupNote({ id: 'T-1' })
    await client.getProject('a/b')
    expect(call(fetchMock, 0).url).toBe('/api/notes/lookup/?path=02-Work%2FA+b.md')
    expect(call(fetchMock, 1).url).toBe('/api/notes/lookup/?id=T-1')
    expect(call(fetchMock, 2).url).toBe('/api/projects/a%2Fb/')
  })

  it('answers a blank search without a request', async () => {
    const { client, fetchMock } = setup()
    expect(await client.search('   ')).toEqual({ query: '   ', results: [] })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('turns the 404 of an unstarted standup into the preview', async () => {
    const preview = { Done: [], Today: ['- [ ] x'], Blockers: [], 'Decisions / Updates': [], 'Follow-ups': [], 'Related Tasks / Projects': [] }
    const { client } = setup(json({ exists: false, preview }, 404))
    expect(await client.getStandupToday()).toEqual({ exists: false, preview })
  })

  it('refreshes the index, then returns the status', async () => {
    setCookie('t')
    const status = { last_pass_at: null, duration_ms: 5, counts_by_type: {}, problems: {}, test_mode: null }
    const { client, fetchMock } = setup(json({ duration_ms: 5 }), json(status))
    expect(await client.refreshIndex()).toEqual(status)
    expect([call(fetchMock, 0).method, call(fetchMock, 0).url]).toEqual(['POST', '/api/index/refresh/'])
    expect([call(fetchMock, 1).method, call(fetchMock, 1).url]).toEqual(['GET', '/api/index/status/'])
  })

  it('returns the 503 health body as an error status', async () => {
    const { client } = setup(json({ status: 'error' }, 503))
    expect(await client.health()).toEqual({ status: 'error' })
  })
})

describe('errors', () => {
  const failure = async (response: Response, run: (c: ReturnType<typeof createHttpClient>) => Promise<unknown>) => {
    setCookie('t')
    try {
      await run(setup(response).client)
    } catch (e) {
      return e as ApiError
    }
    throw new Error('did not reject')
  }

  it('maps 409 with candidates', async () => {
    const e = await failure(json({ detail: 'Several notes have that id.', candidates: ['a.md', 'b.md'] }, 409), (c) => c.lookupNote({ id: 'x' }))
    expect(e).toBeInstanceOf(ApiError)
    expect(e.status).toBe(409)
    expect(e.message).toBe('Several notes have that id.')
    expect(e.body.candidates).toEqual(['a.md', 'b.md'])
  })

  it('maps a partial triage with created_target', async () => {
    const e = await failure(json({ detail: 'Capture changed.', created_target: '02-Work/Tasks/X.md' }, 409), (c) =>
      c.triageCapture({ path: 'a.md', expected_hash: 'h', action: 'task' }),
    )
    expect([e.status, e.body.created_target]).toEqual([409, '02-Work/Tasks/X.md'])
  })

  it.each([400, 404, 422])('maps %i with its detail', async (status) => {
    const e = await failure(json({ detail: `d${status}` }, status), (c) => c.getProject('x'))
    expect([e.status, e.message, e.body.detail]).toEqual([status, `d${status}`, `d${status}`])
  })

  it('says to wait on 429, whatever the body says', async () => {
    const e = await failure(json({ detail: 'Request was throttled. Expected available in 41 seconds.' }, 429), (c) => c.login({ username: 'u', password: 'p' }))
    expect(e.status).toBe(429)
    expect(e.message).toMatch(/too many attempts/i)
  })

  it('handles a non-JSON error body and a network failure', async () => {
    const html = await failure(new Response('<html>Bad gateway</html>', { status: 502 }), (c) => c.getDashboard())
    expect([html.status, html.message]).toEqual([502, 'The server could not complete the request. Try again in a moment.'])
    const down = createHttpClient({ fetch: vi.fn<typeof fetch>().mockRejectedValue(new TypeError('failed')) })
    await expect(down.getDashboard()).rejects.toMatchObject({ status: 0 })
  })
})

describe('session loss', () => {
  const wired = (...responses: Response[]) => {
    setCookie('t')
    const { client } = setup(...responses)
    const gone = vi.fn()
    client.onUnauthenticated(gone)
    return { client, gone }
  }

  it.each([401, 403])('tells listeners on %i from a session endpoint, and still rejects', async (status) => {
    const { client, gone } = wired(json({ detail: 'Authentication credentials were not provided.' }, status))
    await expect(client.getDashboard()).rejects.toMatchObject({ status })
    expect(gone).toHaveBeenCalledTimes(1)
  })

  it('does not treat a CSRF failure as a lost session', async () => {
    // The second 403 is the answer to the one automatic retry.
    const { client, gone } = wired(json({ detail: 'CSRF failed.' }, 403), json({ detail: 'CSRF failed.' }, 403))
    await expect(client.createCapture({ text: 'x' })).rejects.toMatchObject({ status: 403, message: 'CSRF failed.' })
    expect(gone).not.toHaveBeenCalled()
  })

  it('on a CSRF failure fetches a fresh cookie and retries the write once', async () => {
    setCookie('stale')
    const { client, fetchMock } = setup(json({ detail: 'CSRF failed.' }, 403), empty(), empty())
    await client.logout()
    expect(fetchMock.mock.calls.map(([url, init]) => `${init?.method} ${String(url)}`)).toEqual([
      'POST /api/auth/logout/',
      'GET /api/auth/csrf/',
      'POST /api/auth/logout/',
    ])
  })

  it('treats a malformed csrftoken cookie as missing', () => {
    document.cookie = 'csrftoken=%E0%A4%A; path=/'
    expect(readCsrfCookie()).toBeNull()
  })

  it('does not treat a 403 NotAuthenticated body on login as a lost session', async () => {
    const { client, gone } = wired(json({ detail: 'Authentication credentials were not provided.' }, 403))
    await expect(client.login({ username: 'u', password: 'bad' })).rejects.toMatchObject({ status: 403 })
    expect(gone).not.toHaveBeenCalled()
  })

  it('stops calling a listener that unsubscribed', async () => {
    setCookie('t')
    const { client } = setup(json({}, 401))
    const gone = vi.fn()
    client.onUnauthenticated(gone)()
    await expect(client.getDashboard()).rejects.toBeInstanceOf(ApiError)
    expect(gone).not.toHaveBeenCalled()
  })
})

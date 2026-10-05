import { describe, expect, it } from 'vitest'
import { ApiError } from './client'
import { listAllNotes } from './listAll'
import { createMockClient } from './mock/mockClient'
import { DEFAULT_STATUS, STATUS_VOCABULARY } from './types'

const client = (options = {}) => createMockClient({ delayMs: 0, today: '2026-10-06', ...options })
const rejection = async (p: Promise<unknown>) => {
  try {
    await p
  } catch (e) {
    return e as ApiError
  }
  throw new Error('expected a rejection')
}

describe('pagination', () => {
  it('returns next while more results remain, and null on the last page', async () => {
    const c = client()
    const first = await c.listNotes({ type: 'task', page_size: 5 })
    expect(first.count).toBe(14)
    expect(first.results).toHaveLength(5)
    expect(first.next).toBe('/api/notes/?page=2&page_size=5')
    const last = await c.listNotes({ type: 'task', page_size: 5, page: 3 })
    expect(last.results).toHaveLength(4)
    expect(last.next).toBeNull()
    expect(last.previous).toBe('/api/notes/?page=2&page_size=5')
  })
  it('defaults to 100 per page', async () => {
    const c = client()
    for (let i = 0; i < 100; i++) await c.createNote({ type: 'task', title: `Bulk ${i}` })
    const page = await c.listNotes({ type: 'task' })
    expect(page.count).toBe(114)
    expect(page.results).toHaveLength(100)
    expect(page.next).not.toBeNull()
  })
  it('listAllNotes follows next across pages until it is null, without duplicates', async () => {
    const c = client()
    for (let i = 0; i < 100; i++) await c.createNote({ type: 'task', title: `Bulk ${i}` })
    const all = await listAllNotes(c, { type: 'task', ordering: 'path' })
    expect(all).toHaveLength(114)
    expect(new Set(all.map((n) => n.path)).size).toBe(114)
  })
  it('listAllNotes honours a small page size', async () => {
    expect(await listAllNotes(client(), { type: 'task', page_size: 4 })).toHaveLength(14)
  })
})

describe('vocabularies', () => {
  it('has a default status inside each vocabulary', () => {
    for (const type of Object.keys(DEFAULT_STATUS) as (keyof typeof DEFAULT_STATUS)[]) {
      expect(STATUS_VOCABULARY[type]).toContain(DEFAULT_STATUS[type])
    }
  })
  it('gives a created decision the decision default', async () => {
    expect((await client().createNote({ type: 'decision', title: 'D' })).status).toBe('proposed')
  })
})

describe('notes', () => {
  it('looks a note up by path with body, hash, backlinks and a link map', async () => {
    const c = client()
    const note = await c.lookupNote({ path: '02-Work/Tasks/Fix N+1 query on account listing.md' })
    expect(note.content_hash).toMatch(/^sha256:/)
    expect(note.body).toContain('## Description')
    expect(note.links.LoadUp).toEqual({ path: '02-Work/Projects/LoadUp.md', state: 'resolved' })
    const project = await c.lookupNote({ path: '02-Work/Projects/LoadUp.md' })
    expect(project.backlinks.map((b) => b.title)).toContain('Fix N+1 query on account listing')
  })
  it('rejects 404 for an unknown path', async () => {
    expect((await rejection(client().lookupNote({ path: 'nope.md' }))).status).toBe(404)
  })
  it('rejects 409 with the candidate paths when an id matches several notes', async () => {
    const c = client()
    const a = await c.createNote({ type: 'task', title: 'Twin A' })
    await c.createNote({ type: 'task', title: 'Twin B' })
    const error = await rejection(c.lookupNote({ id: a.id as string }))
    expect(error.status).toBe(409)
    expect(error.body.candidates).toEqual(['02-Work/Tasks/Twin A.md', '02-Work/Tasks/Twin B.md'])
  })
  it('rejects 409 on a name collision and 422 on an unknown project', async () => {
    const c = client()
    expect((await rejection(c.createNote({ type: 'task', title: 'rotate staging api credentials' }))).status).toBe(409)
    expect((await rejection(c.createNote({ type: 'task', title: 'X', project: 'ghost' }))).status).toBe(422)
  })
})

describe('changeStatus', () => {
  const path = '02-Work/Tasks/Rotate staging API credentials.md'
  it('changes status with the current hash and appends evidence under Notes when done', async () => {
    const c = client()
    const before = await c.lookupNote({ path })
    const after = await c.changeStatus({ path, status: 'done', expected_hash: before.content_hash, evidence: 'Rotated and verified.' })
    expect(after.status).toBe('done')
    expect(after.body).toContain('- Rotated and verified.')
    expect(after.content_hash).not.toBe(before.content_hash)
  })
  it('rejects 409 for a stale hash', async () => {
    expect((await rejection(client().changeStatus({ path, status: 'done', expected_hash: 'sha256:old' }))).status).toBe(409)
  })
  it('rejects 422 for a status outside the type\'s vocabulary', async () => {
    const c = client()
    const { content_hash } = await c.lookupNote({ path })
    expect((await rejection(c.changeStatus({ path, status: 'accepted', expected_hash: content_hash }))).status).toBe(422)
  })
})

describe('content hash revisions', () => {
  it('changes after every write, so a hash from before the first write is stale', async () => {
    const c = client()
    const created = await c.createNote({ type: 'task', title: 'Fresh task' })
    const path = created.path
    const first = (await c.lookupNote({ path })).content_hash
    const changed = await c.changeStatus({ path, status: 'in-progress', expected_hash: first })
    expect(changed.content_hash).not.toBe(first)
    const error = await rejection(c.changeStatus({ path, status: 'done', expected_hash: first }))
    expect(error.status).toBe(409)
    await expect(c.changeStatus({ path, status: 'done', expected_hash: changed.content_hash })).resolves.toMatchObject({ status: 'done' })
  })
})

describe('triageCapture', () => {
  const capture = '00-Inbox/2026-10-06 0912 todo: renew the staging TLS certificate before the.md'
  it('creates the target and marks the capture triaged', async () => {
    const c = client()
    const { content_hash } = await c.lookupNote({ path: capture })
    const result = await c.triageCapture({ path: capture, expected_hash: content_hash, action: 'task', classification: 'task', title: 'Renew TLS' })
    expect(result.target?.path).toBe('02-Work/Tasks/Renew TLS.md')
    expect(result.capture.status).toBe('triaged')
  })
  it('on a stale capture reports created_target, and a retry with existing_target only edits the capture', async () => {
    const c = client()
    const error = await rejection(c.triageCapture({ path: capture, expected_hash: 'sha256:stale', action: 'task', classification: 'task', title: 'Renew TLS' }))
    expect(error.status).toBe(409)
    expect(error.body.created_target).toBe('02-Work/Tasks/Renew TLS.md')
    const { content_hash } = await c.lookupNote({ path: capture })
    const retry = await c.triageCapture({ path: capture, expected_hash: content_hash, action: 'task', classification: 'task', existing_target: error.body.created_target })
    expect(retry.capture.status).toBe('triaged')
    expect((await c.listNotes({ type: 'task', page_size: 100 })).results.filter((n) => n.title === 'Renew TLS')).toHaveLength(1)
  })
  it('dismisses without a target', async () => {
    const c = client()
    const { content_hash } = await c.lookupNote({ path: capture })
    const result = await c.triageCapture({ path: capture, expected_hash: content_hash, action: 'dismiss', classification: 'note' })
    expect(result).toMatchObject({ target: null, capture: { status: 'dismissed' } })
  })
})

describe('projects, auth and health', () => {
  it('returns a project with open tasks, decisions and recent notes, and 404 for an unknown slug', async () => {
    const c = client()
    const p = await c.getProject('ipp')
    expect(p.open_tasks.every((t) => t.status !== 'done')).toBe(true)
    expect(p.decisions.length).toBeGreaterThan(0)
    expect(p.recent_notes.length).toBeLessThanOrEqual(5)
    expect((await rejection(c.getProject('ghost'))).status).toBe(404)
  })
  it('answers me, login, logout, csrf and health', async () => {
    const c = client()
    expect(await c.me()).toEqual({ username: 'raymark' })
    expect(await c.login({ username: 'raymark', password: 'x' })).toEqual({ username: 'raymark' })
    expect((await rejection(c.login({ username: '', password: '' }))).status).toBe(400)
    await expect(c.logout()).resolves.toBeUndefined()
    await expect(c.csrf()).resolves.toBeUndefined()
    expect(await c.health()).toEqual({ status: 'ok' })
  })
})

describe('standup', () => {
  it('serves a preview, then created, then appends with the note hash', async () => {
    const c = client()
    const before = await c.getStandupToday()
    expect(before.exists).toBe(false)
    if (before.exists) return
    expect(before.preview.Today).toHaveLength(5)
    const started = await c.startStandup()
    expect(started).toMatchObject({ created: true, filled: true })
    const note = await c.appendToStandup({ section: 'Follow-ups', text: '- [ ] Ask infra', expected_hash: started.note.content_hash })
    expect(note.body).toContain('- [ ] Ask infra')
    expect((await rejection(c.appendToStandup({ section: 'Done', text: '- x', expected_hash: started.note.content_hash }))).status).toBe(409)
    expect(await c.startStandup()).toMatchObject({ created: false, filled: false })
  })
  it('fills an untouched note and returns a touched one unchanged', async () => {
    expect(await client({ standup: 'untouched' }).startStandup()).toMatchObject({ created: false, filled: true })
    const touched = client({ standup: 'touched' })
    const before = await touched.getStandupToday()
    expect(await touched.startStandup()).toMatchObject({ created: false, filled: false })
    const after = await touched.getStandupToday()
    expect(before.exists && after.exists && after.note.content_hash).toBe(before.exists && before.note.content_hash)
  })
  it('refuses to append before the note exists', async () => {
    expect((await rejection(client().appendToStandup({ section: 'Done', text: '- x', expected_hash: 'h' }))).status).toBe(404)
  })
})

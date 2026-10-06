import { isForToday, isOpen, isOverdue, priorityRank } from '@/domain/tasks'
import { ApiError, type ApiClient } from '../client'
import {
  DEFAULT_STATUS,
  STANDUP_SECTIONS,
  STATUS_VOCABULARY,
  type CreateNoteRequest,
  type IndexStatus,
  type LinkState,
  type NoteDetail,
  type NoteListParams,
  type NoteSummary,
  type Paginated,
  type ProjectSummary,
  type SearchResponse,
  type StandupPreview,
  type StandupSection,
  type StandupToday,
  type TriageRequest,
} from '../types'
import {
  FIXTURE_TODAY,
  captureBodies,
  captureClassifications,
  captureFixtures,
  captureName,
  dailyBodies,
  dailyFixtures,
  decisionFixtures,
  indexProblemFixtures,
  lessonFixtures,
  projectFixtures,
  projectNoteFixtures,
  taskFixtures,
} from './fixtures'

export type StandupScenario = 'missing' | 'untouched' | 'touched'

export interface MockClientOptions {
  /** The vault's "today". Defaults to the fixture date. */
  today?: string
  /** Artificial latency per call, so loading states are real. */
  delayMs?: number
  /** Whether today's daily note exists, and whether it was edited. */
  standup?: StandupScenario
  /** Local wall-clock time used for notes the client creates. */
  nowTime?: string
}

const FOLDERS = { task: '02-Work/Tasks', decision: '05-Knowledge/Decisions', lesson: '05-Knowledge/Lessons', project: '02-Work/Projects' }
const DEFAULT_PAGE_SIZE = 100

/**
 * In-memory implementation of the whole API for the review build. It follows
 * the contract in `types.ts`, including the 404, 409 and 422 errors the real
 * writer returns, and keeps state so a write shows up on the next read.
 */
export function createMockClient(options: MockClientOptions = {}): ApiClient {
  const today = options.today ?? FIXTURE_TODAY
  const delayMs = options.delayMs ?? 250
  const nowTime = options.nowTime ?? '14:41'
  const now = () => `${today}T${nowTime}:00+08:00`
  const stamp = () => `${today.replace(/-/g, '')}${nowTime.replace(':', '')}00`
  const standupPath = `01-Daily/${today.slice(0, 4)}/${today}.md`

  const notes: NoteSummary[] = [
    ...taskFixtures(),
    ...projectNoteFixtures(),
    ...decisionFixtures(),
    ...lessonFixtures(),
    ...dailyFixtures(),
    ...captureFixtures(),
  ]
  const projects: ProjectSummary[] = projectFixtures()
  const bodies = dailyBodies()
  captureBodies().forEach((body, path) => bodies.set(path, body))
  const classifications = captureClassifications()
  // A finished task with the evidence line the Dashboard's Done recently shows.
  bodies.set(
    '02-Work/Tasks/Reproduce duplicate settlement rows.md',
    '## Description\n\nFind where duplicate rows enter the settlement file.\n\n## Notes\n\n- Reproduced on staging: a retried callback wrote the row twice.\n\n## Links\n\n- [[IPP]]\n',
  )
  // Revision per note path: every write increments it, and the content hash is built from it.
  const revisions = new Map<string, number>()
  const bump = (path: string) => revisions.set(path, (revisions.get(path) ?? 0) + 1)

  // Today's daily note: its state, the lines added since, and a revision for its hash.
  let standup: StandupScenario | 'filled' = options.standup ?? 'missing'
  let standupRevision = 0
  const standupAdded: Record<string, string[]> = {}
  let lastPass = `${today}T14:39:52+08:00`

  const wait = <T>(value: () => T): Promise<T> =>
    new Promise((resolve, reject) =>
      setTimeout(() => {
        try {
          resolve(value())
        } catch (error) {
          reject(error)
        }
      }, delayMs),
    )

  const tasks = () => notes.filter((n) => n.type === 'task')
  const byDue = (a: NoteSummary, b: NoteSummary) => (a.due ?? '9999').localeCompare(b.due ?? '9999') || a.title.localeCompare(b.title)

  /** Carry-forward rule (plan section 2.2): what the standup would list. */
  const carryToday = () => {
    const rank: Record<string, number> = { 'in-progress': 0, review: 1, planned: 2 }
    return tasks()
      .filter((t) => isForToday(t, today))
      .sort((a, b) => rank[a.status ?? ''] - rank[b.status ?? ''] || byDue(a, b))
  }
  const carryBlocked = () => tasks().filter((t) => t.status === 'blocked').sort(byDue)

  const projectTitle = (slug: string | null) => projects.find((p) => p.slug === slug)?.title ?? slug ?? ''

  const withOpenCounts = (): ProjectSummary[] =>
    projects.map((p) => ({ ...p, open_task_count: tasks().filter((t) => t.project === p.slug && isOpen(t)).length }))

  // ---- today's daily note -------------------------------------------------

  const carryForward = (): StandupPreview => ({
    Done: [],
    Today: carryToday().map((t) => `- [ ] [[${t.title}]]`),
    Blockers: carryBlocked().map((t) => `- [[${t.title}]]${t.blocked_by ? ` (blocked by: ${t.blocked_by})` : ''}`),
    'Decisions / Updates': [],
    'Follow-ups': [],
    'Related Tasks / Projects': [
      ...new Set([...carryToday(), ...carryBlocked()].map((t) => t.project).filter((slug): slug is string => !!slug && projects.some((p) => p.slug === slug))),
    ]
      .map(projectTitle)
      .sort()
      .map((title) => `- [[${title}]]`),
  })

  const standupSections = (): StandupPreview => {
    const base: StandupPreview =
      standup === 'filled'
        ? carryForward()
        : {
            Done: [],
            Today: standup === 'touched' ? ['- [ ] Pair with QA on the OTP reproduction'] : [],
            Blockers: [],
            'Decisions / Updates': [],
            'Follow-ups': [],
            'Related Tasks / Projects': [],
          }
    for (const section of STANDUP_SECTIONS) base[section] = [...base[section], ...(standupAdded[section] ?? [])]
    return base
  }

  const standupBody = () => {
    const sections = standupSections()
    return `# Standup - ${today}\n\n${STANDUP_SECTIONS.map((h) => `## ${h}\n\n${sections[h].join('\n')}\n`).join('\n')}`
  }

  const standupNote = (): NoteSummary => ({
    ...dailyFixtures()[0],
    id: `${today.replace(/-/g, '')}093000`,
    path: standupPath,
    title: today,
    created: today,
    modified: `${today}T14:41:00+08:00`,
  })

  const dailyNote = (): NoteSummary[] => (standup === 'missing' ? [] : [standupNote()])
  const allNotes = () => [...notes, ...dailyNote()]

  // ---- note detail ---------------------------------------------------------

  const hashOf = (n: NoteSummary) => (n.path === standupPath ? `sha256:mock-standup-${standupRevision}` : `sha256:mock-${n.path}@r${revisions.get(n.path) ?? 0}`)

  const defaultBody = (n: NoteSummary) => {
    if (n.path === standupPath) return standupBody()
    const link = n.project ? `\n- [[${projectTitle(n.project)}]]` : ''
    return n.type === 'task' ? `## Description\n\n## Notes\n\n## Links\n${link}\n` : `## Notes\n${link}\n`
  }

  const detail = (n: NoteSummary): NoteDetail => {
    const body = n.path === standupPath ? standupBody() : (bodies.get(n.path) ?? defaultBody(n))
    const links: NoteDetail['links'] = {}
    for (const match of body.matchAll(/\[\[([^\]|#]+)/g)) {
      const target = match[1].trim()
      const hits = allNotes().filter((x) => x.title.toLowerCase() === target.toLowerCase())
      const state: LinkState = hits.length === 1 ? 'resolved' : hits.length > 1 ? 'ambiguous' : 'unresolved'
      links[target] = { path: hits.length === 1 ? hits[0].path : null, state }
    }
    return {
      ...n,
      frontmatter: {
        type: n.type,
        id: n.id,
        status: n.status,
        priority: n.priority,
        project: n.project,
        created: n.created,
        due: n.due,
        tags: n.tags,
        ...(classifications.has(n.path) ? { classification: classifications.get(n.path) } : {}),
      },
      body,
      content_hash: hashOf(n),
      backlinks: allNotes()
        .filter((x) => x.path !== n.path && (bodies.get(x.path) ?? defaultBody(x)).includes(`[[${n.title}]]`))
        .map((x) => ({ path: x.path, title: x.title })),
      links,
    }
  }

  const find = (path: string) => {
    const note = allNotes().find((n) => n.path === path)
    if (!note) throw new ApiError(404, `No note at ${path}.`)
    return note
  }

  // ---- writes --------------------------------------------------------------

  function create(input: CreateNoteRequest): NoteSummary {
    const folder = FOLDERS[input.type]
    const title = input.title.trim()
    if (notes.some((n) => n.path.toLowerCase() === `${folder}/${title}.md`.toLowerCase())) {
      throw new ApiError(409, `A note with this name already exists in ${folder}. Nothing was written.`)
    }
    const project = input.project ? projects.find((p) => p.slug === input.project || p.title === input.project) : undefined
    if (input.project && !project) throw new ApiError(422, `Unknown project: ${input.project}.`)
    const note: NoteSummary = {
      id: stamp(),
      path: `${folder}/${title}.md`,
      type: input.type,
      title,
      status: input.status ?? DEFAULT_STATUS[input.type],
      priority: input.type === 'task' ? (input.priority ?? 'medium') : null,
      project: project?.slug ?? null,
      due: input.due || null,
      blocked_by: null,
      decided: null,
      tags: [],
      created: today,
      modified: now(),
      parse_error: null,
    }
    notes.push(note)
    bump(note.path)
    if (input.type === 'project') {
      projects.push({ slug: title.toLowerCase().replace(/\s+/g, '-'), title, path: note.path, status: note.status, goal: null, open_task_count: 0, modified: note.modified })
    }
    if (input.body) bodies.set(note.path, input.body)
    return note
  }

  function indexStatus(): IndexStatus {
    const counts: Record<string, number> = {}
    allNotes().forEach((n) => {
      counts[n.type] = (counts[n.type] ?? 0) + 1
    })
    return { last_pass_at: lastPass, duration_ms: 700, counts_by_type: counts, problems: indexProblemFixtures(), test_mode: null }
  }

  const getStandup = (): StandupToday =>
    standup === 'missing'
      ? { exists: false, preview: carryForward() }
      : { exists: true, note: detail(standupNote()), untouched: standup === 'untouched' }

  return {
    onUnauthenticated: () => () => undefined,
    csrf: () => wait(() => undefined),
    login: ({ username, password }) =>
      wait(() => {
        if (!username.trim() || !password) throw new ApiError(400, 'Enter a username and a password.')
        return { username: username.trim() }
      }),
    logout: () => wait(() => undefined),
    me: () => wait(() => ({ username: 'raymark' })),
    health: () => wait(() => ({ status: 'ok' as const })),

    listNotes: (params: NoteListParams = {}) =>
      wait<Paginated<NoteSummary>>(() => {
        const rows = allNotes()
          .filter((n) => !params.type || n.type === params.type)
          .filter((n) => !params.status?.length || params.status.includes(n.status ?? ''))
          .filter((n) => !params.priority || n.priority === params.priority)
          .filter((n) => !params.project || n.project === params.project)
          .filter((n) => !params.tag || n.tags.includes(params.tag))
          .filter((n) => !params.overdue || isOverdue(n, today))
          .filter((n) => !params.path_prefix || n.path.startsWith(params.path_prefix))
        const ordering = params.ordering ?? '-modified'
        const key = ordering.replace('-', '') as 'modified' | 'due' | 'title' | 'path'
        rows.sort((a, b) => {
          const sign = ordering.startsWith('-') ? -1 : 1
          const av = (a[key] ?? '9999') as string
          const bv = (b[key] ?? '9999') as string
          return sign * av.localeCompare(bv) || priorityRank(a.priority) - priorityRank(b.priority) || a.path.localeCompare(b.path)
        })
        const size = params.page_size ?? DEFAULT_PAGE_SIZE
        const page = params.page ?? 1
        const link = (n: number) => `/api/notes/?page=${n}&page_size=${size}`
        return {
          count: rows.length,
          next: page * size < rows.length ? link(page + 1) : null,
          previous: page > 1 ? link(page - 1) : null,
          results: rows.slice((page - 1) * size, page * size),
        }
      }),

    lookupNote: (by) =>
      wait(() => {
        if ('path' in by) return detail(find(by.path))
        const hits = allNotes().filter((n) => n.id === by.id)
        if (!hits.length) throw new ApiError(404, `No note with id ${by.id}.`)
        if (hits.length > 1) throw new ApiError(409, `Id ${by.id} matches ${hits.length} notes.`, { candidates: hits.map((n) => n.path) })
        return detail(hits[0])
      }),

    createNote: (input) => wait(() => create(input)),

    changeStatus: ({ path, status, expected_hash, evidence }) =>
      wait(() => {
        const note = find(path)
        if (note.parse_error) throw new ApiError(422, `${path} has malformed frontmatter. Fix it in Obsidian first.`)
        if (hashOf(note) !== expected_hash) throw new ApiError(409, `${path} changed in Obsidian. Reload and try again.`)
        const vocabulary = (STATUS_VOCABULARY as Record<string, readonly string[]>)[note.type]
        if (!vocabulary?.includes(status)) throw new ApiError(422, `${status} is not a status for a ${note.type} note.`)
        note.status = status
        note.modified = now()
        bump(path)
        if (note.type === 'decision' && status === 'accepted') note.decided = today
        if (status === 'done' && evidence) {
          const body = bodies.get(path) ?? defaultBody(note)
          bodies.set(path, body.replace('## Notes\n', `## Notes\n\n- ${evidence}\n`))
        }
        return detail(note)
      }),

    createCapture: ({ text }) =>
      wait(() => {
        const name = captureName(today, nowTime.replace(':', ''), text.trim())
        const note: NoteSummary = {
          id: stamp(),
          path: `00-Inbox/${name}.md`,
          type: 'capture',
          title: name,
          status: DEFAULT_STATUS.capture,
          priority: null,
          project: null,
          due: null,
          blocked_by: null,
          decided: null,
          tags: [],
          created: today,
          modified: now(),
          parse_error: null,
        }
        notes.push(note)
        bodies.set(note.path, `${text.trim()}\n`)
        bump(note.path)
        return note
      }),

    triageCapture: (input: TriageRequest) =>
      wait(() => {
        const capture = find(input.path)
        if (capture.type !== 'capture') throw new ApiError(422, `${input.path} is not a capture.`)
        let target: NoteSummary | null = null
        if (input.action === 'task' || input.action === 'decision' || input.action === 'lesson' || input.action === 'project') {
          if (input.existing_target) {
            target = notes.find((n) => n.path === input.existing_target) ?? null
            if (!target) throw new ApiError(422, `${input.existing_target} does not exist.`)
          } else {
            target = create({ type: input.action, title: input.title?.trim() || capture.title, project: input.project })
          }
        }
        // The target is written first; a stale capture then fails with the target already on disk.
        if (hashOf(capture) !== input.expected_hash) {
          throw new ApiError(409, `${input.path} changed in Obsidian. The new note was created; retry to finish triage.`, target ? { created_target: target.path } : {})
        }
        if (input.action !== 'dismiss' && input.classification) classifications.set(capture.path, input.classification)
        capture.status = input.action === 'dismiss' ? 'dismissed' : input.action === 'keep' ? 'inbox' : 'triaged'
        capture.modified = now()
        bump(capture.path)
        return { capture: detail(capture), target }
      }),

    listProjects: () => wait(() => withOpenCounts()),

    getProject: (slug) =>
      wait(() => {
        const project = withOpenCounts().find((p) => p.slug === slug)
        if (!project) throw new ApiError(404, `No project with slug ${slug}.`)
        const mine = allNotes().filter((n) => n.project === slug)
        return {
          project,
          note: detail(find(project.path)),
          open_tasks: mine.filter((n) => n.type === 'task' && isOpen(n)).sort(byDue),
          decisions: mine.filter((n) => n.type === 'decision'),
          recent_notes: mine.slice().sort((a, b) => b.modified.localeCompare(a.modified) || a.path.localeCompare(b.path)).slice(0, 5),
        }
      }),

    getStandupToday: () => wait(getStandup),

    startStandup: () =>
      wait(() => {
        const created = standup === 'missing'
        const filled = created || standup === 'untouched'
        if (filled) {
          standup = 'filled'
          standupRevision += 1
        }
        return { created, filled, note: detail(standupNote()), untouched: false }
      }),

    appendToStandup: ({ section, text, expected_hash }) =>
      wait(() => {
        if (standup === 'missing') throw new ApiError(404, `${standupPath} does not exist. Start the standup first.`)
        if (expected_hash !== `sha256:mock-standup-${standupRevision}`) throw new ApiError(409, `${standupPath} changed in Obsidian. Reload and try again.`)
        if (!text.trim()) throw new ApiError(422, 'Nothing to append.')
        if (standup === 'untouched') standup = 'touched'
        // The writer adds the list marker by the section's rule: a checkbox under Today and Follow-ups, a plain bullet elsewhere.
        const marker = section === 'Today' || section === 'Follow-ups' ? '- [ ] ' : '- '
        ;(standupAdded[section as StandupSection] ??= []).push(`${marker}${text.trim()}`)
        standupRevision += 1
        return { note: detail(standupNote()), section_created: false }
      }),

    getDashboard: () =>
      wait(() => ({
        today,
        today_tasks: carryToday(),
        in_progress: tasks().filter((t) => t.status === 'in-progress'),
        blocked: carryBlocked(),
        overdue: tasks().filter((t) => isOverdue(t, today)),
        standup: getStandup(),
        // Captures are left out so the list reads like the approved prototype; the real API will include them.
        recent_activity: allNotes()
          .filter((n) => n.type !== 'capture')
          .sort((a, b) => b.modified.localeCompare(a.modified) || a.path.localeCompare(b.path))
          .slice(0, 7),
        active_projects: withOpenCounts().filter((p) => p.status === 'active'),
        inbox_count: notes.filter((n) => n.type === 'capture' && n.status === 'inbox').length,
        index: {
          last_pass_at: lastPass,
          problem_count: Object.values(indexProblemFixtures()).reduce((n, list) => n + list.length, 0),
        },
      })),

    search: (query: string) =>
      wait<SearchResponse>(() => {
        const q = query.trim().toLowerCase()
        const results = q
          ? allNotes()
              .filter((n) => n.title.toLowerCase().includes(q))
              .map((n) => ({ path: n.path, type: n.type, title: n.title, project: n.project, snippet: 'Title match', source: 'vault' as const }))
          : []
        return { query, results }
      }),

    getIndexStatus: () => wait(indexStatus),

    refreshIndex: () =>
      wait(() => {
        lastPass = `${today}T14:41:07+08:00`
        return indexStatus()
      }),
  }
}

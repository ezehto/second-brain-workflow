import type { NoteSummary, Priority } from '@/api/types'

/** A task with only the fields a test cares about. */
export function task(title: string, overrides: Partial<NoteSummary> = {}): NoteSummary {
  return {
    id: null,
    path: `02-Work/Tasks/${title}.md`,
    type: 'task',
    title,
    status: 'planned',
    priority: null as Priority | null,
    project: null,
    due: null,
    blocked_by: null,
    decided: null,
    tags: [],
    created: '2026-10-01',
    modified: '2026-10-05T10:00:00+08:00',
    parse_error: null,
    ...overrides,
  }
}

import { useCallback, useMemo } from 'react'
import { useApi } from '@/api/ApiProvider'
import { listAllNotes } from '@/api/listAll'
import { useQuery, type Query } from '@/api/useQuery'
import type { NoteSummary, ProjectSummary } from '@/api/types'
import { dateOfDailyPath, parseDaily, type DailyDay } from '@/domain/daily'
import { linkResolver, type LinkResolver } from './links'

/** How many of the newest daily notes are read in full, for the patterns. */
export const HISTORY_DEPTH = 14

export interface History {
  /** Every daily note, newest first (`ordering: -path`). */
  list: NoteSummary[]
  /** The newest `HISTORY_DEPTH` of them, parsed, newest first. */
  days: DailyDay[]
}

export function useHistory(): Query<History> {
  const client = useApi()
  return useQuery(
    useCallback(async () => {
      const list = await listAllNotes(client, { type: 'daily', ordering: '-path' })
      const details = await Promise.all(list.slice(0, HISTORY_DEPTH).map((n) => client.lookupNote({ path: n.path })))
      const days = details.map((d) => ({ date: dateOfDailyPath(d.path), path: d.path, sections: parseDaily(d.body) }))
      return { list, days }
    }, [client]),
  )
}

/** Projects and tasks, for turning wikilinks into links and lines into projects. Empty until loaded. */
export function useResolver(note?: Parameters<typeof linkResolver>[2]): LinkResolver {
  const client = useApi()
  const projects: Query<ProjectSummary[]> = useQuery(useCallback(() => client.listProjects(), [client]))
  const tasks: Query<NoteSummary[]> = useQuery(useCallback(() => listAllNotes(client, { type: 'task', ordering: 'path' }), [client]))
  const projectData = projects.status === 'success' ? projects.data : undefined
  const taskData = tasks.status === 'success' ? tasks.data : undefined
  return useMemo(() => linkResolver(projectData ?? [], taskData ?? [], note), [projectData, taskData, note])
}

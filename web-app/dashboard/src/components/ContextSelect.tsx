import { useCallback } from 'react'
import { useSearchParams } from 'react-router'
import { useApi } from '@/api/ApiProvider'
import { useQuery } from '@/api/useQuery'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { PROJECT_PARAM, useProjectContext } from '@/lib/projectContext'

const ALL = 'all'

/**
 * The project context switcher. It writes the `project` query parameter and
 * leaves every other parameter alone; pages read the parameter to filter
 * (decision 2), and the rail and tab bar carry it across navigation.
 */
export function ContextSelect({ className }: { className?: string }) {
  const client = useApi()
  const projects = useQuery(useCallback(() => client.listProjects(), [client]))
  const [, setParams] = useSearchParams()
  const current = useProjectContext()

  const active = projects.status === 'success' ? projects.data.filter((p) => p.status === 'active') : []
  // A project in the URL that is paused or unknown still shows, so the filter is never invisible.
  const extra = current && !active.some((p) => p.slug === current) ? current : null

  function choose(value: string) {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (value === ALL) next.delete(PROJECT_PARAM)
        else next.set(PROJECT_PARAM, value)
        return next
      },
      { replace: true },
    )
  }

  return (
    <Select value={current ?? ALL} onValueChange={choose}>
      <SelectTrigger aria-label="Project" className={className ?? 'w-44'}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>All projects</SelectItem>
        {active.map((p) => (
          <SelectItem key={p.slug} value={p.slug}>
            {p.title}
          </SelectItem>
        ))}
        {extra && <SelectItem value={extra}>{extra}</SelectItem>}
      </SelectContent>
    </Select>
  )
}

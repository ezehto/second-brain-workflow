import { Link } from 'react-router'
import type { ProjectSummary } from '@/api/types'
import { Segmented } from '@/components/Segmented'
import { tasksHref, type TaskFilters } from '@/lib/routes'
import { GROUPS, hasFilters, type GroupBy } from './filters'

const SELECT =
  't-body h-8 min-w-0 cursor-pointer rounded-btn border border-line bg-inset px-2 font-normal text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand max-rail:min-h-11'

const GROUP_LABEL: Record<GroupBy, string> = { project: 'Project', status: 'Status', due: 'Due' }

/** Project, priority, overdue and today filters plus the grouping, all written to the URL by the page. */
export function FilterBar({
  filters,
  group,
  projects,
  onFilters,
  onGroup,
}: {
  filters: TaskFilters
  group: GroupBy
  projects: ProjectSummary[]
  onFilters: (change: Partial<TaskFilters>) => void
  onGroup: (group: GroupBy) => void
}) {
  // A `project` in the URL that is not in the list (a typo, a deleted note) stays selectable so the filter is visible.
  const known = projects.some((p) => p.slug === filters.project)
  return (
    <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
      <label className="flex flex-col gap-0.5">
        <span className="t-small text-muted-ink">Project</span>
        <select className={SELECT} value={filters.project ?? ''} onChange={(e) => onFilters({ project: e.target.value || undefined })}>
          <option value="">All projects</option>
          {filters.project && !known && <option value={filters.project}>{filters.project} (unknown)</option>}
          {projects.map((p) => (
            <option key={p.slug} value={p.slug}>
              {p.title}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-0.5">
        <span className="t-small text-muted-ink">Priority</span>
        <select className={SELECT} value={filters.priority ?? ''} onChange={(e) => onFilters({ priority: e.target.value || undefined })}>
          <option value="">Any priority</option>
          <option value="high">P1, high</option>
          <option value="medium">P2, medium</option>
          <option value="low">P3, low</option>
        </select>
      </label>
      <label className="t-body flex min-h-8 items-center gap-2 max-rail:min-h-11">
        <input type="checkbox" className="size-4 accent-brand-fill" checked={!!filters.overdue} onChange={(e) => onFilters({ overdue: e.target.checked || undefined })} />
        Overdue only
      </label>
      <label className="t-body flex min-h-8 items-center gap-2 max-rail:min-h-11">
        <input type="checkbox" className="size-4 accent-brand-fill" checked={!!filters.today} onChange={(e) => onFilters({ today: e.target.checked || undefined })} />
        For today
      </label>
      {hasFilters(filters) && (
        <Link to={tasksHref()} className="t-body flex min-h-8 items-center max-rail:min-h-11">
          Clear filters
        </Link>
      )}
      <div className="ml-auto flex items-center gap-2">
        <span className="t-small font-semibold text-muted-ink">Group by</span>
        <Segmented label="Group by" value={group} onChange={onGroup} options={GROUPS.map((g) => ({ value: g, label: GROUP_LABEL[g] }))} />
      </div>
    </div>
  )
}

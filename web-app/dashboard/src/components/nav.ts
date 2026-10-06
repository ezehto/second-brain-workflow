import { routes } from '@/lib/routes'
import type { IconName } from './Icon'

export interface NavItem {
  label: string
  to: string
  icon: IconName
}
export interface NavGroup {
  label: string
  items: NavItem[]
  /** A collapsed group the person can open; its state is remembered. */
  collapsible?: boolean
}

/** The rail (assessment 5.1). Previews sit under a collapsed "Later" group so they stop looking broken. */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Today',
    items: [
      { label: 'Today', to: routes.dashboard, icon: 'dashboard' },
      { label: 'Standup', to: routes.standups, icon: 'standup' },
      { label: 'Inbox', to: routes.inbox, icon: 'inbox' },
    ],
  },
  {
    label: 'Work',
    items: [
      { label: 'Tasks', to: routes.tasks, icon: 'tasks' },
      { label: 'Projects', to: routes.projects, icon: 'projects' },
    ],
  },
  {
    label: 'Knowledge',
    items: [
      { label: 'Knowledge', to: routes.knowledge, icon: 'knowledge' },
      { label: 'Decisions', to: routes.decisions, icon: 'decisions' },
      { label: 'Search', to: routes.search, icon: 'search' },
    ],
  },
  { label: 'System', items: [{ label: 'Index status', to: routes.indexStatus, icon: 'index' }] },
  {
    label: 'Later',
    collapsible: true,
    items: [
      { label: 'Workflow', to: routes.workflow, icon: 'workflow' },
      { label: 'Timeline', to: routes.timeline, icon: 'timeline' },
      { label: 'Upskilling', to: routes.upskilling, icon: 'upskilling' },
    ],
  },
]

/** The bottom tab bar on phone and tablet; everything else is under More. */
export const TAB_ITEMS: NavItem[] = [
  NAV_GROUPS[0].items[0],
  NAV_GROUPS[1].items[0],
  NAV_GROUPS[0].items[1],
  NAV_GROUPS[1].items[1],
]

import { routes } from '@/lib/routes'
import type { IconName } from './Icon'

export interface NavItem {
  label: string
  to: string
  icon: IconName
  /** Not part of Phase 1: the page is a preview or later work. */
  preview?: boolean
}
export interface NavGroup {
  label: string
  items: NavItem[]
}

/** The rail. Group and item order are from the approved prototype. */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Today',
    items: [
      { label: 'Dashboard', to: routes.dashboard, icon: 'dashboard' },
      { label: 'Standup', to: routes.standups, icon: 'standup' },
      { label: 'Inbox', to: routes.inbox, icon: 'inbox' },
    ],
  },
  {
    label: 'Work',
    items: [
      { label: 'Tasks', to: routes.tasks, icon: 'tasks' },
      { label: 'Projects', to: routes.projects, icon: 'projects' },
      { label: 'Workflow', to: routes.workflow, icon: 'workflow', preview: true },
      { label: 'Timeline', to: routes.timeline, icon: 'timeline', preview: true },
    ],
  },
  {
    label: 'Knowledge',
    items: [
      { label: 'Knowledge', to: routes.knowledge, icon: 'knowledge' },
      { label: 'Decisions', to: routes.decisions, icon: 'decisions' },
      { label: 'Upskilling', to: routes.upskilling, icon: 'upskilling', preview: true },
    ],
  },
  {
    label: 'System',
    items: [
      { label: 'Search', to: routes.search, icon: 'search' },
      { label: 'Index status', to: routes.indexStatus, icon: 'index' },
    ],
  },
]

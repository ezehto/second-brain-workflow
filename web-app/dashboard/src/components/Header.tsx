import { useCallback, useState, type FormEvent } from 'react'
import { Link, useMatches, useNavigate } from 'react-router'
import { useApi } from '@/api/ApiProvider'
import { useQuery } from '@/api/useQuery'
import { useToday } from '@/lib/clock'
import { NOT_AVAILABLE, formatTimeOfDay } from '@/lib/dates'
import { projectHref, routes } from '@/lib/routes'
import { indexProblemCount } from '@/domain/indexStatus'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Icon } from './Icon'
import { QuickActions } from './QuickActions'
import { Segmented } from './Segmented'
import { resolveText, type PageHandle } from './pageHandle'
import type { IndexStatus } from '@/api/types'

/** Page title and subtitle, search, context switcher, index status, user, and the quick actions. */
export function Header({ index, todayKnown }: { index: IndexStatus | undefined; todayKnown: boolean }) {
  const client = useApi()
  const today = useToday()
  const navigate = useNavigate()
  const handle = useMatches().at(-1)?.handle as PageHandle | undefined
  const [query, setQuery] = useState('')
  const projects = useQuery(useCallback(() => client.listProjects(), [client]))
  const me = useQuery(useCallback(() => client.me(), [client]))

  const lastPass = index?.last_pass_at ? formatTimeOfDay(index.last_pass_at) : null
  const ctx = { today, lastPass }
  // Until the server has said what day it is, a date title would be a guess.
  const title = handle && todayKnown ? resolveText(handle.title, ctx) : ''
  const subtitle = handle && todayKnown ? resolveText(handle.subtitle, ctx) : ''
  const username = me.status === 'success' ? me.data.username : null
  const problems = index ? indexProblemCount(index) : null

  function onSearch(event: FormEvent) {
    event.preventDefault()
    const q = query.trim()
    navigate(q ? `${routes.search}?q=${encodeURIComponent(q)}` : routes.search)
  }

  const active = projects.status === 'success' ? projects.data.filter((p) => p.status === 'active') : []

  return (
    <header className="flex flex-col gap-4 px-4 pt-5 pb-2 rail:px-7">
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-[1_1_320px]">
          <h1 className={handle?.display ? 'day' : 'page-title'}>{title}</h1>
          <p className="m-0 text-muted-ink">{subtitle}</p>
        </div>
        <form role="search" onSubmit={onSearch} className="relative flex max-w-[380px] flex-[1_1_180px] items-center">
          <label htmlFor="vault-search" className="sr-only">
            Search the vault
          </label>
          <span className="pointer-events-none absolute left-3 flex text-muted-ink">
            <Icon name="search" className="size-[18px]" />
          </span>
          <Input id="vault-search" type="search" placeholder="Search the vault" className="pl-[38px]" value={query} onChange={(e) => setQuery(e.target.value)} />
        </form>
        <Segmented
          label="Context"
          value="all"
          options={[
            { value: 'all', label: 'All projects', href: routes.dashboard },
            ...active.map((p) => ({ value: p.slug, label: p.title, href: projectHref(p.slug) })),
          ]}
        />
        <Button asChild variant="secondary" size="sm">
          <Link to={routes.indexStatus}>
            <span className="num">Indexed {lastPass ?? NOT_AVAILABLE}</span>
            {problems !== null && (
              <span className={`num rounded-full px-2 py-px text-xs font-bold ${problems ? 'bg-tint-blocked text-status-blocked' : 'bg-line text-ink'}`}>
                <span className="sr-only">Problems: </span>
                {problems}
              </span>
            )}
          </Link>
        </Button>
        <div className="flex items-center gap-2.5">
          <span title={username ?? undefined} className="inline-flex size-9 items-center justify-center rounded-full bg-brand-soft font-bold text-brand-hover">
            <span aria-hidden="true">{username ? username[0].toUpperCase() : '?'}</span>
            <span className="sr-only">{username ? `Signed in as ${username}` : 'User not available'}</span>
          </span>
          <span className="hidden text-muted-ink 2xl:inline" aria-hidden="true">
            {username ?? NOT_AVAILABLE}
          </span>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <QuickActions />
        <div className="flex-1" />
        <Button asChild size="sm">
          <Link to={routes.standups}>Start standup</Link>
        </Button>
      </div>
    </header>
  )
}

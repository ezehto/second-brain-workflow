import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useMatches, useNavigate } from 'react-router'
import { useApi } from '@/api/ApiProvider'
import { useQuery } from '@/api/useQuery'
import type { IndexStatus } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useToday } from '@/lib/clock'
import { formatTimeOfDay } from '@/lib/dates'
import { PROJECT_PARAM, useProjectContext, useProjectHref } from '@/lib/projectContext'
import { routes } from '@/lib/routes'
import { useMinWidth, type Viewport } from '@/lib/viewport'
import { indexErrorCount } from '@/domain/indexStatus'
import { CommandPalette, useCommandPaletteShortcut } from './CommandPalette'
import { ContextSelect } from './ContextSelect'
import { Icon } from './Icon'
import { usePublishedTitle } from './PageTitle'
import { NewMenu } from './QuickActions'
import { resolveText, type PageHandle } from './pageHandle'

/** The width from which the header holds the full search box. */
const SEARCH_BOX_MIN_WIDTH = 1100

/**
 * The top bar: 52px (48px on a phone). Page title, with the date as the title
 * on Today, and the route's subtitle under it; search with a Ctrl+K hint; the
 * project context select; the New menu; an index pill (from 832px) only when the index has
 * problems; the avatar. On a phone it shrinks to title, search icon and New,
 * and the context select moves into the More sheet (also on a tablet, into the menu).
 */
export function Header({
  index,
  todayKnown,
  viewport,
  onOpenMenu,
}: {
  index: IndexStatus | undefined
  todayKnown: boolean
  viewport: Viewport
  onOpenMenu: () => void
}) {
  const client = useApi()
  const today = useToday()
  const navigate = useNavigate()
  const project = useProjectContext()
  const href = useProjectHref()
  const handle = useMatches().at(-1)?.handle as PageHandle | undefined
  const [query, setQuery] = useState('')
  const searchRef = useRef<HTMLInputElement>(null)
  const me = useQuery(useCallback(() => client.me(), [client]))

  const phone = viewport === 'phone'
  // Below 1100px the search box would be squeezed to a few characters: it becomes an icon that opens the palette.
  const roomyForSearch = useMinWidth(SEARCH_BOX_MIN_WIDTH)
  const tablet = viewport === 'tablet'

  const [paletteOpen, setPaletteOpen] = useState(false)
  const openPalette = useCallback(() => setPaletteOpen(true), [setPaletteOpen])
  useCommandPaletteShortcut(openPalette)

  const lastPass = index?.last_pass_at ? formatTimeOfDay(index.last_pass_at) : null
  const ctx = { today, lastPass }
  // Until the server has said what day it is, a date title would be a guess.
  const published = usePublishedTitle()
  const title = handle && todayKnown ? (published ?? resolveText(handle.title, ctx)) : ''
  const subtitle = handle && todayKnown ? resolveText(handle.subtitle, ctx) : ''
  // Warnings stay in the rail's count; the top bar is for what is broken.
  const problems = index ? indexErrorCount(index) : 0
  const username = me.status === 'success' ? me.data.username : null

  const tabLabel = handle && todayKnown ? (handle.label ?? title) : ''
  useEffect(() => {
    document.title = tabLabel ? `${tabLabel} · Second Brain` : 'Second Brain'
  }, [tabLabel])

  function onSearch(event: FormEvent) {
    event.preventDefault()
    const params = new URLSearchParams()
    if (query.trim()) params.set('q', query.trim())
    if (project) params.set(PROJECT_PARAM, project)
    const qs = params.toString()
    navigate(qs ? `${routes.search}?${qs}` : routes.search)
  }

  return (
    <header className="sticky top-0 z-30 flex h-12 items-center gap-3 border-b border-line bg-ground px-4 sm:h-[52px] rail:px-6">
      {tablet && (
        <Button variant="secondary" size="icon" onClick={onOpenMenu} aria-label="Open navigation">
          <Icon name="menu" className="size-5" />
        </Button>
      )}

      <div className="min-w-0 flex-1 sm:flex-none sm:basis-52 rail:basis-72">
        <h1 className="page-title truncate">{title}</h1>
        {!phone && <p className="t-small m-0 truncate text-muted-ink">{subtitle}</p>}
      </div>

      {phone ? (
        <Button asChild variant="secondary" size="icon" aria-label="Search">
          <Link to={project ? `${routes.search}?${PROJECT_PARAM}=${encodeURIComponent(project)}` : routes.search}>
            <Icon name="search" className="size-[18px]" />
          </Link>
        </Button>
      ) : !roomyForSearch ? (
        <Button variant="secondary" size="icon" aria-label="Search the vault (Ctrl K)" title="Search the vault (Ctrl K)" onClick={openPalette}>
          <Icon name="search" className="size-[18px]" />
        </Button>
      ) : (
        <form role="search" onSubmit={onSearch} className="relative flex min-w-[140px] max-w-[420px] flex-[3_1_0] items-center">
          <label htmlFor="vault-search" className="sr-only">
            Search the vault
          </label>
          <span className="pointer-events-none absolute left-3 flex text-muted-ink">
            <Icon name="search" className="size-4" />
          </span>
          <Input
            id="vault-search"
            ref={searchRef}
            type="search"
            placeholder="Search the vault"
            className="pr-14 pl-9"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <kbd className="t-caption pointer-events-none absolute right-2 rounded border border-line px-1 font-sans text-muted-ink" aria-hidden="true">
            Ctrl K
          </kbd>
        </form>
      )}

      {!phone && <div className="flex-1" />}

      {!phone && !tablet && <ContextSelect />}
      <NewMenu iconOnly={phone} />
      {!phone && !tablet && problems > 0 && (
        <Button asChild variant="secondary" size="sm" className="bg-tint-blocked text-status-blocked hover:bg-tint-blocked">
          <Link to={href.link(routes.indexStatus)}>
            <span className="num">{problems}</span> index {problems === 1 ? 'error' : 'errors'}
          </Link>
        </Button>
      )}
      {!phone && (
        <span title={username ?? undefined} className="inline-flex size-8 flex-none items-center justify-center rounded-full bg-brand-soft font-bold text-brand-hover">
          <span aria-hidden="true">{username ? username[0].toUpperCase() : '?'}</span>
          <span className="sr-only">{username ? `Signed in as ${username}` : 'User not available'}</span>
        </span>
      )}
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </header>
  )
}

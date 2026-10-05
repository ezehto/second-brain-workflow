import type { ApiClient } from './client'
import type { NoteListParams, NoteSummary } from './types'

const MAX_PAGES = 200

/** The `page` number a DRF `next` link points at, or null. */
function pageOf(next: string): number | null {
  const page = new URL(next, 'http://api.invalid').searchParams.get('page')
  return page ? Number(page) : null
}

/**
 * Every note matching `params`, following `next` until it is null. The API
 * pages (plan section 5), so a page that needs a complete set (the dashboard
 * counts) must use this rather than assume one page is everything.
 */
export async function listAllNotes(client: ApiClient, params: Omit<NoteListParams, 'page'> = {}): Promise<NoteSummary[]> {
  const all: NoteSummary[] = []
  let page: number | null = 1
  for (let i = 0; page !== null && i < MAX_PAGES; i++) {
    const response = await client.listNotes({ ...params, page })
    all.push(...response.results)
    const nextPage: number | null = response.next ? pageOf(response.next) : null
    page = nextPage !== null && nextPage !== page ? nextPage : null
  }
  return all
}

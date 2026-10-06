import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createMockClient } from '@/api/mock/mockClient'
import { indexProblemFixtures } from '@/api/mock/fixtures'
import { ApiError, type ApiClient } from '@/api/client'
import { INDEX_PROBLEM_CATEGORIES, type IndexStatus } from '@/api/types'
import { mockClient, renderInApp } from '@/test/helpers'
import { CATEGORY_LABELS } from './categories'
import { IndexStatusPage } from './IndexStatusPage'

const base = async (): Promise<IndexStatus> => createMockClient({ delayMs: 0 }).getIndexStatus()
const emptyProblems = (): IndexStatus['problems'] => ({ ...indexProblemFixtures(), ...Object.fromEntries(INDEX_PROBLEM_CATEGORIES.map((k) => [k, []])) })

function clientWith(overrides: Partial<ApiClient>): ApiClient {
  return { ...mockClient(), ...overrides }
}
const section = (label: string) => screen.getByRole('listitem', { name: label })

describe('IndexStatusPage', () => {
  it('shows the last pass, duration, notes indexed and problem count', async () => {
    renderInApp(<IndexStatusPage />)
    expect(await screen.findByText('Last pass')).toBeInTheDocument()
    expect(screen.getByText('2026-10-06 14:39')).toBeInTheDocument()
    expect(screen.getByText('0.7 s')).toBeInTheDocument()
    expect(screen.getByText('Problems').nextSibling).toHaveTextContent('8')
  })

  it('renders every category with its count and affected notes linking to the reader', async () => {
    renderInApp(<IndexStatusPage />)
    await screen.findByText('Problems by category')
    const fixtures = indexProblemFixtures()
    for (const key of INDEX_PROBLEM_CATEGORIES) {
      const items = fixtures[key]
      const li = section(CATEGORY_LABELS[key])
      if (items.length === 0) {
        expect(within(li).getByText('None')).toBeInTheDocument()
        continue
      }
      expect(within(li).getByText(`${items.length} ${items.length === 1 ? 'note' : 'notes'}`)).toBeInTheDocument()
      for (const item of items) {
        expect(within(li).getByRole('link', { name: item.path })).toHaveAttribute('href', `/notes?path=${encodeURIComponent(item.path)}`)
        expect(within(li).getByText(item.detail)).toBeInTheDocument()
      }
    }
    expect(within(section('Duplicate project slugs')).getByText('None')).toBeInTheDocument()
  })

  it('shows None for every category when there are no problems', async () => {
    renderInApp(<IndexStatusPage />, clientWith({ getIndexStatus: async () => ({ ...(await base()), problems: emptyProblems() }) }))
    await screen.findByText('Problems by category')
    expect(screen.getAllByText('None')).toHaveLength(8)
  })

  it('draws a bar and a number for each note type', async () => {
    renderInApp(<IndexStatusPage />, clientWith({ getIndexStatus: async () => ({ ...(await base()), counts_by_type: { task: 12, decision: 3 } }) }))
    await screen.findByText('Notes by type')
    expect(screen.getByText('task').parentElement).toHaveTextContent('12')
    expect(screen.getByText('decision').parentElement).toHaveTextContent('3')
  })

  it('shows the test-mode line only when test_mode is set', async () => {
    const { unmount } = renderInApp(<IndexStatusPage />)
    await screen.findByText('Last pass')
    expect(screen.queryByText(/Test mode/)).not.toBeInTheDocument()
    unmount()
    renderInApp(<IndexStatusPage />, clientWith({ getIndexStatus: async () => ({ ...(await base()), test_mode: { today: '2026-10-06' } }) }))
    expect(await screen.findByText('Test mode: today is pinned to 2026-10-06.')).toBeInTheDocument()
  })

  it('lists Jira, GitLab and Calendar as not connected, with a preview badge', async () => {
    renderInApp(<IndexStatusPage />)
    const block = (await screen.findByRole('heading', { name: 'Integrations' })).closest('section')!
    for (const name of ['Jira', 'GitLab', 'Calendar']) expect(within(block).getByText(name)).toBeInTheDocument()
    expect(within(block).getAllByText('Not connected')).toHaveLength(3)
    expect(within(block).getByText('Preview')).toBeInTheDocument()
  })

  it('shows an error state with a retry when the status cannot load', async () => {
    renderInApp(<IndexStatusPage />, clientWith({ getIndexStatus: () => Promise.reject(new Error('boom')) }))
    expect(await screen.findByRole('alert')).toHaveTextContent('boom')
  })

  describe('Refresh index', () => {
    it('calls the endpoint once, disables while running, shows the summary and refetches', async () => {
      let release!: (s: IndexStatus) => void
      const refreshIndex = vi.fn(() => new Promise<IndexStatus>((r) => (release = r)))
      const getIndexStatus = vi.fn(base)
      renderInApp(<IndexStatusPage />, clientWith({ refreshIndex, getIndexStatus }))
      const button = await screen.findByRole('button', { name: 'Refresh index' })
      expect(getIndexStatus).toHaveBeenCalledTimes(1)

      await userEvent.click(button)
      const busy = screen.getByRole('button', { name: 'Refreshing' })
      expect(busy).toBeDisabled()
      await userEvent.click(busy)
      expect(refreshIndex).toHaveBeenCalledTimes(1)

      release({ ...(await base()), duration_ms: 900, counts_by_type: { task: 5, note: 2 } })
      expect(await screen.findByText(/Pass finished in 0.9 s: 7 notes indexed, 8 problems\./)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Refresh index' })).toBeEnabled()
      await waitFor(() => expect(getIndexStatus).toHaveBeenCalledTimes(2))
      expect(refreshIndex).toHaveBeenCalledTimes(1)
    })

    it('shows an error and re-enables the button when the pass fails', async () => {
      const refreshIndex = vi.fn(() => Promise.reject(new ApiError(500, 'Indexer crashed')))
      renderInApp(<IndexStatusPage />, clientWith({ refreshIndex }))
      await userEvent.click(await screen.findByRole('button', { name: 'Refresh index' }))
      expect(await screen.findByText(/Could not refresh the index. Indexer crashed/)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Refresh index' })).toBeEnabled()
      expect(screen.queryByText(/Pass finished/)).not.toBeInTheDocument()
    })
  })
})

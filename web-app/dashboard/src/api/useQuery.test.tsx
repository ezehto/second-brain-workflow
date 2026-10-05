import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { mockClient } from '@/test/helpers'
import { ApiProvider, useInvalidate } from './ApiProvider'
import { useQuery } from './useQuery'

const wrapper = ({ children }: { children: ReactNode }) => <ApiProvider client={mockClient()}>{children}</ApiProvider>

describe('useQuery', () => {
  it('returns loading, not the previous question\'s data, when the fetcher changes', async () => {
    const first = () => Promise.resolve('first')
    const pending = () => new Promise<string>(() => {})
    const { result, rerender } = renderHook(({ fetcher }) => useQuery(fetcher), { wrapper, initialProps: { fetcher: first } })
    await waitFor(() => expect(result.current.data).toBe('first'))
    rerender({ fetcher: pending })
    expect(result.current.status).toBe('loading')
    expect(result.current.data).toBeUndefined()
  })

  it('keeps the data on screen while an invalidate refetches the same question', async () => {
    let calls = 0
    let release: (v: string) => void = () => {}
    const fetcher = () => {
      calls += 1
      return calls === 1 ? Promise.resolve('one') : new Promise<string>((resolve) => (release = resolve))
    }
    const { result } = renderHook(() => ({ q: useQuery(fetcher), invalidate: useInvalidate() }), { wrapper })
    await waitFor(() => expect(result.current.q.data).toBe('one'))
    act(() => result.current.invalidate())
    await waitFor(() => expect(calls).toBe(2))
    expect(result.current.q.status).toBe('success')
    expect(result.current.q.data).toBe('one')
    await act(async () => release('two'))
    await waitFor(() => expect(result.current.q.data).toBe('two'))
  })

  it('drops a late answer to a question that is no longer asked', async () => {
    let releaseOld: (v: string) => void = () => {}
    const old = () => new Promise<string>((resolve) => (releaseOld = resolve))
    const next = () => Promise.resolve('new')
    const { result, rerender } = renderHook(({ fetcher }) => useQuery(fetcher), { wrapper, initialProps: { fetcher: old } })
    rerender({ fetcher: next })
    await waitFor(() => expect(result.current.data).toBe('new'))
    await act(async () => releaseOld('old'))
    expect(result.current.data).toBe('new')
  })
})

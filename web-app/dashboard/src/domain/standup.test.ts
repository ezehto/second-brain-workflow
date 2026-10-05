import { describe, expect, it } from 'vitest'
import { createMockClient } from '@/api/mock/mockClient'
import { dailyPath, sectionLines, summarizeStandup } from './standup'

const body = '# Standup - 2026-10-06\n\n## Done\n\n## Today\n\n- [ ] [[A]]\n- [ ] Plain\n\n## Blockers\n\n- [[B]] (blocked by: x)\n'

describe('standup summary', () => {
  it('reads list lines under a heading and stops at the next one', () => {
    expect(sectionLines(body, 'Today')).toEqual(['- [ ] [[A]]', '- [ ] Plain'])
    expect(sectionLines(body, 'Blockers')).toHaveLength(1)
    expect(sectionLines(body, 'Follow-ups')).toEqual([])
  })
  it('summarises a missing note from its carry-forward preview', async () => {
    const client = createMockClient({ delayMs: 0, today: '2026-10-06' })
    expect(summarizeStandup(await client.getStandupToday(), '2026-10-06')).toEqual({
      path: dailyPath('2026-10-06'),
      exists: false,
      untouched: null,
      today_count: 5,
      blocker_count: 2,
    })
  })
  it('summarises an existing note from its body', async () => {
    const client = createMockClient({ delayMs: 0, today: '2026-10-06', standup: 'touched' })
    expect(summarizeStandup(await client.getStandupToday(), '2026-10-06')).toMatchObject({ exists: true, untouched: false, today_count: 1, blocker_count: 0 })
  })
})

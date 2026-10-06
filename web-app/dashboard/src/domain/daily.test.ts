import { describe, expect, it } from 'vitest'
import { STANDUP_SECTIONS } from '@/api/types'
import {
  carryOverItems,
  dateOfDailyPath,
  openFollowUps,
  openRuns,
  parseDaily,
  parseLine,
  previousDay,
  recurringBlockers,
  standupAsText,
  standupCounts,
  textSegments,
  workByProject,
  type DailyDay,
} from './daily'

const body = (parts: Partial<Record<(typeof STANDUP_SECTIONS)[number], string[]>>) =>
  `# Standup\n\n${STANDUP_SECTIONS.map((h) => `## ${h}\n\n${(parts[h] ?? []).join('\n')}\n`).join('\n')}`

const day = (date: string, parts: Parameters<typeof body>[0]): DailyDay => ({ date, path: `01-Daily/2026/${date}.md`, sections: parseDaily(body(parts)) })

describe('parseLine', () => {
  it('reads checkbox state, links and the key', () => {
    expect(parseLine('- [ ] [[Fix N+1 query]]')).toMatchObject({ checked: false, links: ['Fix N+1 query'], key: 'fix n+1 query' })
    expect(parseLine('- [x] Pair with  QA')).toMatchObject({ checked: true, text: 'Pair with  QA', key: 'pair with qa' })
    expect(parseLine('- [/] half done')).toMatchObject({ checked: true, text: 'half done' })
    expect(parseLine('- [-] dropped')).toMatchObject({ checked: true })
    expect(parseLine('- plain bullet')).toMatchObject({ checked: null, links: [] })
  })
  it('drops the alias and heading of a wikilink', () => {
    expect(parseLine('- [[Fix thing#Notes|the fix]] today').links).toEqual(['Fix thing'])
  })
})

describe('textSegments', () => {
  it('splits text and links, using the alias as the label', () => {
    expect(textSegments('see [[A|alpha]] and [[B]]!')).toEqual([
      { kind: 'text', value: 'see ' },
      { kind: 'link', target: 'A', label: 'alpha' },
      { kind: 'text', value: ' and ' },
      { kind: 'link', target: 'B', label: 'B' },
      { kind: 'text', value: '!' },
    ])
  })
})

describe('parseDaily', () => {
  it('splits the six sections and leaves a missing heading empty', () => {
    const s = parseDaily('## Done\n\n- [x] a\n\n## Today\n\n- [ ] b\n- [ ] c\n')
    expect(s.Done).toHaveLength(1)
    expect(s.Today.map((l) => l.text)).toEqual(['b', 'c'])
    expect(s.Blockers).toEqual([])
  })
})

describe('dates', () => {
  it('reads the date of a daily path', () => expect(dateOfDailyPath('01-Daily/2026/2026-10-06.md')).toBe('2026-10-06'))
  it('finds the latest day before a date, across a weekend', () => {
    const days = [{ date: '2026-10-05' }, { date: '2026-10-02' }, { date: '2026-10-06' }]
    expect(previousDay(days, '2026-10-06')?.date).toBe('2026-10-05')
    expect(previousDay(days, '2026-10-05')?.date).toBe('2026-10-02')
    expect(previousDay(days, '2026-10-02')).toBeNull()
  })
})

describe('carry-over items', () => {
  const days = [
    day('2026-10-06', { Today: ['- [ ] [[Rotate keys]]', '- [ ] [[New]]'] }),
    day('2026-10-05', { Today: ['- [ ] [[Rotate keys]]', '- [ ] [[New]]'] }),
    day('2026-10-02', { Today: ['- [ ] [[Rotate keys]]'] }),
    day('2026-10-01', { Today: ['- [ ] [[Rotate keys]]'] }),
  ]
  it('lists items in Today for 3 or more standups in a row, with the run start', () => {
    const items = carryOverItems(days)
    expect(items.map((i) => i.label)).toEqual(['Rotate keys'])
    expect(items[0]).toMatchObject({ standups: 4, since: '2026-10-01' })
  })
  it('breaks the run when the item was checked off or missing', () => {
    const broken = [days[0], days[1], day('2026-10-02', { Today: ['- [x] [[Rotate keys]]'] }), days[3]]
    expect(openRuns(broken, 'Today').find((r) => r.key === 'rotate keys')?.standups).toBe(2)
    expect(carryOverItems(broken)).toEqual([])
  })
  it('does not count an item marked [/] or [-] as open', () => {
    expect(openRuns([day('2026-10-06', { Today: ['- [/] [[A]]', '- [-] [[B]]', '- [ ] [[C]]'] })], 'Today').map((r) => r.label)).toEqual(['C'])
    const days = [day('2026-10-06', { Today: ['- [ ] [[A]]'] }), day('2026-10-05', { Today: ['- [/] [[A]]'] })]
    expect(openRuns(days, 'Today')[0].standups).toBe(1)
  })
  it('does not list an item that is not in the newest standup', () => {
    expect(carryOverItems([day('2026-10-06', {}), ...days.slice(1)])).toEqual([])
  })
})

describe('recurringBlockers', () => {
  it('counts the days a blocker is listed, needs two, and keeps the blocked-by text', () => {
    const days = [
      day('2026-10-06', { Blockers: ['- [[Confirm rate limit]] (blocked by: provider)', '- [[Once]]'] }),
      day('2026-10-05', { Blockers: ['- [[Confirm rate limit]] (blocked by: provider)'] }),
      day('2026-10-02', { Blockers: ['- Waiting on staging', '- [[Confirm rate limit]]'] }),
    ]
    const result = recurringBlockers(days)
    expect(result).toHaveLength(1)
    expect(result[0]).toMatchObject({ label: 'Confirm rate limit', dates: ['2026-10-02', '2026-10-05', '2026-10-06'], blockedBy: 'provider' })
  })
})

describe('workByProject', () => {
  it('counts Done lines over the last five standups only', () => {
    const days = [
      day('2026-10-06', { Done: ['- [x] [[a]]'] }),
      day('2026-10-05', { Done: ['- [x] [[a]]', '- [x] [[b]]', '- [x] free text'] }),
      day('2026-10-04', {}),
      day('2026-10-03', {}),
      day('2026-10-02', {}),
      day('2026-10-01', { Done: ['- [x] [[a]]'] }),
    ]
    const projectOf = (l: { links: string[] }) => ({ a: 'ipp', b: 'loadup' })[l.links[0] as 'a' | 'b'] ?? null
    expect(workByProject(days, projectOf)).toEqual([
      { slug: 'ipp', count: 2 },
      { slug: 'loadup', count: 1 },
      { slug: null, count: 1 },
    ])
  })
})

describe('openFollowUps', () => {
  it('lists unchecked follow-ups with their age, and drops one checked in the newest note', () => {
    const days = [
      day('2026-10-06', { 'Follow-ups': ['- [ ] Ask QA for the UAT slot', '- [x] Sent the report'] }),
      day('2026-10-02', { 'Follow-ups': ['- [ ] Ask QA for the UAT slot', '- [ ] Sent the report'] }),
    ]
    const result = openFollowUps(days, '2026-10-06')
    expect(result.map((f) => [f.label, f.ageDays])).toEqual([['Ask QA for the UAT slot', 4]])
  })
})

describe('standupCounts', () => {
  it('counts planned, carried, blockers and unchecked follow-ups', () => {
    const days = [day('2026-10-06', { Today: ['- [ ] [[A]]', '- [ ] [[B]]'], Blockers: ['- [[C]]'], 'Follow-ups': ['- [ ] x', '- [x] y'] }), day('2026-10-05', { Today: ['- [ ] [[A]]'] })]
    expect(standupCounts(days[0].sections, openRuns(days, 'Today'))).toEqual({ planned: 2, carried: 1, blockers: 1, followUps: 1 })
  })
})

describe('standupAsText', () => {
  it('writes plain text with links unwrapped and yesterday first', () => {
    const text = standupAsText({
      date: '2026-10-06',
      yesterday: day('2026-10-05', { Done: ['- [x] [[Repro rows|Reproduce rows]]'] }),
      sections: day('2026-10-06', { Today: ['- [ ] [[Fix N+1]]'], 'Related Tasks / Projects': ['- [[IPP]]'] }).sections,
    })
    expect(text).toContain('Standup, Tuesday 6 October')
    expect(text).toContain('Yesterday (Oct 5), done:\n- Reproduce rows')
    expect(text).toContain('Today:\n- Fix N+1')
    expect(text).toContain('Blockers:\n- none')
    expect(text).toContain('Related: IPP')
  })
})

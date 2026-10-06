import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { NoteDetail } from '@/api/types'
import { renderInApp } from '@/test/helpers'
import { NoteMarkdown } from './NoteMarkdown'

const render = (body: string, links: NoteDetail['links'] = {}) => renderInApp(<NoteMarkdown body={body} links={links} />)

describe('NoteMarkdown', () => {
  it('renders Markdown structure', () => {
    render('## Notes\n\n- one\n- **two**\n\n`code`')
    expect(screen.getByRole('heading', { name: 'Notes' })).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText('two').tagName).toBe('STRONG')
  })

  it('shows raw HTML as text and never creates the element or the handler', () => {
    const { container } = render('<script>alert(1)</script>\n\nSee <img src=x onerror=alert(1)> here\n\n<div onclick="steal()">block</div>')
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('[onerror]')).toBeNull()
    expect(container.querySelector('[onclick]')).toBeNull()
    expect(container).toHaveTextContent('<script>alert(1)</script>')
    expect(container).toHaveTextContent('<img src=x onerror=alert(1)>')
    expect(container).toHaveTextContent('onclick="steal()"')
  })

  it('does not load a Markdown image, and drops a javascript: link target', () => {
    const { container } = render('![chart](https://tracker.example/p.png)\n\n[click](javascript:alert(1))')
    expect(container.querySelector('img')).toBeNull()
    expect(container).toHaveTextContent('[image: chart]')
    expect(screen.getByText('click').closest('a')).not.toHaveAttribute('href', expect.stringContaining('javascript'))
  })

  it('opens external links in a new tab with rel noopener noreferrer', () => {
    render('[docs](https://example.com/a) and <https://example.org>')
    for (const link of screen.getAllByRole('link')) {
      expect(link).toHaveAttribute('target', '_blank')
      expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    }
    expect(screen.getByRole('link', { name: 'docs' })).toHaveAttribute('href', 'https://example.com/a')
  })

  it('turns a resolved wikilink into an in-app link to the path the API gave', () => {
    render('See [[Rotate staging API credentials]] and [[Rotate staging API credentials|the rotation]].', {
      'Rotate staging API credentials': { path: '02-Work/Tasks/Rotate staging API credentials.md', state: 'resolved' },
    })
    const links = screen.getAllByRole('link')
    expect(links[0]).toHaveAttribute('href', '/notes?path=02-Work%2FTasks%2FRotate%20staging%20API%20credentials.md')
    expect(links[1]).toHaveTextContent('the rotation')
    expect(links[1]).toHaveAttribute('href', links[0].getAttribute('href')!)
    expect(links[0]).not.toHaveAttribute('target')
  })

  it('marks an ambiguous and an unresolved wikilink in text and does not link them', () => {
    render('[[Twin]] and [[Ghost]] and [[Not in map]]', {
      Twin: { path: null, state: 'ambiguous' },
      Ghost: { path: null, state: 'unresolved' },
    })
    expect(screen.queryByRole('link')).toBeNull()
    expect(screen.getByText('Twin').closest('[data-link-state]')).toHaveAttribute('data-link-state', 'ambiguous')
    expect(screen.getByText('Twin').closest('[data-link-state]')).toHaveTextContent('(ambiguous)')
    expect(screen.getByText('Ghost').closest('[data-link-state]')).toHaveTextContent('(unresolved)')
    expect(screen.getByText('Not in map').closest('[data-link-state]')).toHaveTextContent('(unresolved)')
  })

  it('looks a wikilink up by the spelling the API used, with no normalisation', () => {
    render('[[a Note#Heading]] [[b note]]', {
      'a Note': { path: 'A.md', state: 'resolved' },
      // Case differs from the body: not matched, so unresolved here even though a server might fold case.
      'B note': { path: 'B.md', state: 'resolved' },
    })
    expect(screen.getByRole('link', { name: 'a Note' })).toHaveAttribute('href', '/notes?path=A.md')
    expect(screen.getByText('b note').closest('[data-link-state]')).toHaveAttribute('data-link-state', 'unresolved')
  })

  it('leaves a wikilink inside code as written', () => {
    const { container } = render('`[[Code]]`\n\n```\n[[Block]]\n```', { Code: { path: 'C.md', state: 'resolved' }, Block: { path: 'B.md', state: 'resolved' } })
    expect(screen.queryByRole('link')).toBeNull()
    expect(container).toHaveTextContent('[[Code]]')
    expect(container).toHaveTextContent('[[Block]]')
  })
})

import type { ComponentProps, ElementType } from 'react'
import Markdown, { defaultUrlTransform, type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Link } from 'react-router'
import type { NoteDetail } from '@/api/types'
import { noteHref } from '@/lib/routes'
import { WIKILINK_SCHEME, remarkWikilinks } from './remarkWikilinks'

type Links = NoteDetail['links']

/**
 * The key the API used for a wikilink, taken exactly as the API wrote it
 * ("one entry per spelling as written", plan section 5): the full inner text
 * first, then the part before `|`, then that part without `#heading`. No
 * casefolding or other normalisation happens here; the server resolves.
 */
function linkEntry(inner: string, links: Links): Links[string] | undefined {
  const beforePipe = inner.split('|')[0].trim()
  for (const key of [inner, beforePipe, beforePipe.split('#')[0].trim()]) {
    if (Object.prototype.hasOwnProperty.call(links, key)) return links[key]
  }
  return undefined
}

const URL_SAFE = (url: string) => (url.startsWith(WIKILINK_SCHEME) ? url : defaultUrlTransform(url))
const isExternal = (href: string) => /^(https?:)?\/\//i.test(href) || /^mailto:/i.test(href)

const FLAG = 't-caption ml-1 font-semibold'

function wikilink(href: string, children: ComponentProps<'a'>['children'], links: Links) {
  const inner = decodeURIComponent(href.slice(WIKILINK_SCHEME.length))
  const entry = linkEntry(inner, links)
  if (entry?.state === 'resolved' && entry.path) {
    return (
      <Link to={noteHref(entry.path)} data-link-state="resolved">
        {children}
      </Link>
    )
  }
  const ambiguous = entry?.state === 'ambiguous'
  return (
    <span
      data-link-state={ambiguous ? 'ambiguous' : 'unresolved'}
      title={ambiguous ? 'Several notes have this name. Link by path to pick one.' : 'No note has this name.'}
      className={`border-b border-dashed ${ambiguous ? 'border-status-risk text-status-risk' : 'border-muted-ink text-muted-ink'}`}
    >
      {children}
      <span className={FLAG}>{ambiguous ? '(ambiguous)' : '(unresolved)'}</span>
    </span>
  )
}

/** A markdown element rendered as `Tag` with the app's classes; the hast `node` prop is not passed on to the DOM. */
const styled = (Tag: ElementType, className: string) =>
  function Styled({ node, ...rest }: { node?: unknown } & object) {
    void node
    return <Tag {...rest} className={className} />
  }

function components(links: Links): Components {
  return {
    a({ node, href = '', children, ...rest }) {
      void node
      if (href.startsWith(WIKILINK_SCHEME)) return wikilink(href, children, links)
      if (isExternal(href)) {
        return (
          <a {...rest} href={href} target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        )
      }
      return (
        <a {...rest} href={href}>
          {children}
        </a>
      )
    },
    // An embedded image would make the browser fetch whatever address the note names.
    img: ({ alt }) => <span className="text-muted-ink">[image{alt ? `: ${alt}` : ''}]</span>,
    h1: styled('h3', 't-panel mt-4 mb-2 font-semibold'),
    h2: styled('h3', 't-body mt-4 mb-1 font-bold'),
    h3: styled('h4', 't-body mt-3 mb-1 font-semibold'),
    h4: styled('h4', 't-body mt-3 mb-1 font-semibold'),
    h5: styled('h4', 't-body mt-3 mb-1 font-semibold'),
    h6: styled('h4', 't-body mt-3 mb-1 font-semibold'),
    p: styled('p', 't-body my-2'),
    ul: styled('ul', 'my-2 list-disc pl-6'),
    ol: styled('ol', 'my-2 list-decimal pl-6'),
    blockquote: styled('blockquote', 'my-2 border-l-2 border-line pl-3 text-muted-ink'),
    hr: styled('hr', 'my-4 border-line'),
    pre: styled('pre', 'mono my-2 overflow-x-auto rounded-btn bg-inset p-3'),
    code: styled('code', 'mono rounded-sm bg-inset px-1'),
    table: ({ node, ...rest }) => {
      void node
      return (
        <div className="my-2 overflow-x-auto">
          <table {...rest} className="t-small w-full border-collapse" />
        </div>
      )
    },
    th: styled('th', 'border border-line px-2 py-1 text-left font-semibold'),
    td: styled('td', 'border border-line px-2 py-1'),
  }
}

/**
 * A note's Markdown body. Raw HTML in the note is shown as text (react-markdown
 * does not enable it, and no rehype-raw is added), so `<script>` and `onerror`
 * can never run. Wikilinks become in-app links through the API's `links` map;
 * external links open in a new tab with `rel="noopener noreferrer"`.
 */
export function NoteMarkdown({ body, links }: { body: string; links: Links }) {
  return (
    <div className="max-w-[72ch] break-words">
      <Markdown remarkPlugins={[remarkGfm, remarkWikilinks]} urlTransform={URL_SAFE} components={components(links)}>
        {body}
      </Markdown>
    </div>
  )
}

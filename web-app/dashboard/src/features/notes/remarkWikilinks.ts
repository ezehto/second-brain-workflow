/**
 * The inner text of a wikilink travels on the node as this property, never in
 * the URL: a note's own `[x](wikilink:...)` is author text and must not be
 * mistaken for one, and a malformed escape in it cannot reach a decoder.
 */
export const WIKILINK_PROP = 'data-wikilink'

interface Node {
  type: string
  value?: string
  url?: string
  data?: { hProperties?: Record<string, string> }
  children?: Node[]
}

// Never descend into these: a wikilink inside code or an existing link stays as written.
const OPAQUE = new Set(['code', 'inlineCode', 'html', 'link', 'linkReference', 'definition'])
const WIKILINK = /\[\[([^[\]\n]+?)\]\]/g

function split(text: string): Node[] | null {
  const parts: Node[] = []
  let last = 0
  for (const match of text.matchAll(WIKILINK)) {
    const inner = match[1]
    const target = inner.split('|')[0].split('#')[0].trim()
    const alias = inner.includes('|') ? inner.slice(inner.indexOf('|') + 1).trim() : ''
    if (match.index > last) parts.push({ type: 'text', value: text.slice(last, match.index) })
    parts.push({
      type: 'link',
      url: '#wikilink',
      data: { hProperties: { [WIKILINK_PROP]: inner } },
      children: [{ type: 'text', value: alias || target || inner }],
    })
    last = match.index + match[0].length
  }
  if (!parts.length) return null
  if (last < text.length) parts.push({ type: 'text', value: text.slice(last) })
  return parts
}

function walk(node: Node) {
  if (!node.children) return
  const next: Node[] = []
  for (const child of node.children) {
    if (child.type === 'text' && child.value) next.push(...(split(child.value) ?? [child]))
    else {
      if (!OPAQUE.has(child.type)) walk(child)
      next.push(child)
    }
  }
  node.children = next
}

/** remark plugin: turns `[[Target]]`, `[[Target|alias]]` and `[[Target#Heading]]` in text into link nodes. */
export function remarkWikilinks() {
  return (tree: Node) => walk(tree)
}

import { Fragment } from 'react'

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** Splits `text` into plain and matching parts for the words of `query` (case-insensitive). */
export function splitMatches(text: string, query: string): { text: string; match: boolean }[] {
  const words = [...new Set(query.trim().split(/\s+/).filter(Boolean))].sort((a, b) => b.length - a.length)
  if (!words.length) return [{ text, match: false }]
  // With one capture group, split() puts the matches at the odd indexes.
  const parts = text.split(new RegExp(`(${words.map(escape).join('|')})`, 'i'))
  return parts.map((part, i) => ({ text: part, match: i % 2 === 1 })).filter((p) => p.text !== '')
}

/**
 * Text with the query's words wrapped in `<mark>`. Built from React text nodes,
 * never as HTML, so a snippet from a note cannot inject markup.
 */
export function Highlight({ text, query }: { text: string; query: string }) {
  return (
    <>
      {splitMatches(text, query).map((part, i) => (
        <Fragment key={i}>
          {part.match ? <mark className="rounded-sm bg-line px-px font-bold text-ink">{part.text}</mark> : part.text}
        </Fragment>
      ))}
    </>
  )
}

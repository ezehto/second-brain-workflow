/** The first list line under `## Notes` of a note body, without its bullet: the evidence a done task carries. */
export function evidenceLine(body: string): string | null {
  const lines = body.split('\n')
  const start = lines.findIndex((l) => l.trim() === '## Notes')
  if (start < 0) return null
  for (const line of lines.slice(start + 1)) {
    if (line.startsWith('## ')) return null
    const m = /^[-*+] (?:\[[ xX]\] )?(.+)$/.exec(line.trim())
    if (m) return m[1].trim()
  }
  return null
}

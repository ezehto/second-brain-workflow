import { createContext, useCallback, useContext, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { useApi, useInvalidate } from '@/api/ApiProvider'
import { useQuery } from '@/api/useQuery'
import type { Priority } from '@/api/types'
import { useToday } from '@/lib/clock'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuShortcut, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Icon } from './Icon'
import { useToast } from './Toast'

export type QuickActionKind = 'task' | 'followup' | 'decision' | 'lesson' | 'capture'

const ACTIONS: { kind: QuickActionKind; button: string; title: string; submit: string }[] = [
  { kind: 'task', button: 'Task', title: 'Create task', submit: 'Create task' },
  { kind: 'followup', button: 'Follow-up', title: 'Add follow-up', submit: 'Add follow-up' },
  { kind: 'decision', button: 'Decision', title: 'Record decision', submit: 'Record decision' },
  { kind: 'lesson', button: 'Note', title: 'Add note', submit: 'Create lesson' },
  { kind: 'capture', button: 'Capture', title: 'Capture', submit: 'Capture' },
]

const NO_PROJECT = 'none'
const FOLDER = { task: '02-Work/Tasks/', decision: '05-Knowledge/Decisions/', lesson: '05-Knowledge/Lessons/' } as const

const QuickActionContext = createContext<{ open: (kind: QuickActionKind) => void } | null>(null)

/** Opens one of the five creation dialogs from anywhere in the shell. */
export function useQuickActions() {
  const ctx = useContext(QuickActionContext)
  if (!ctx) throw new Error('useQuickActions must be used inside <QuickActionsProvider>')
  return ctx
}

const SHORTCUT: Record<string, QuickActionKind> = { t: 'task', f: 'followup', d: 'decision', n: 'lesson', c: 'capture' }
const KEY_OF = Object.fromEntries(Object.entries(SHORTCUT).map(([key, kind]) => [kind, key.toUpperCase()])) as Record<QuickActionKind, string>

const SELECT_PARTS = '[role="listbox"], [role="combobox"], [role="option"]'

function isTyping(target: EventTarget | null) {
  const el = target as HTMLElement | null
  if (!el) return false
  // A Radix Select takes letters for typeahead, so its trigger and list never start a shortcut.
  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) || el.isContentEditable || !!el.closest?.(SELECT_PARTS)
}

/**
 * Holds the open creation dialog and the single-key shortcuts that open one
 * (T task, F follow-up, D decision, N note, C capture). A shortcut never fires
 * while typing, with a modifier held, or while another dialog is open.
 */
export function QuickActionsProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState<QuickActionKind | null>(null)
  const value = useMemo(() => ({ open: setOpen }), [])

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.ctrlKey || event.metaKey || event.altKey || event.repeat || isTyping(event.target)) return
      const kind = SHORTCUT[event.key.toLowerCase()]
      if (!kind || document.querySelector('[role="dialog"], [role="menu"], [role="listbox"]')) return
      event.preventDefault()
      setOpen(kind)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  return (
    <QuickActionContext.Provider value={value}>
      {children}
      {open && <QuickActionDialog kind={open} onClose={() => setOpen(null)} />}
    </QuickActionContext.Provider>
  )
}

/** The "New" menu: the five creation dialogs, each with its shortcut shown. */
export function NewMenu({ iconOnly = false }: { iconOnly?: boolean }) {
  const { open } = useQuickActions()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size={iconOnly ? 'icon' : 'sm'} aria-label={iconOnly ? 'New' : undefined}>
          <Icon name="plus" className="size-4" />
          {!iconOnly && 'New'}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-52">
        {ACTIONS.map((a) => (
          <DropdownMenuItem key={a.kind} onSelect={() => open(a.kind)} className="min-h-8 max-rail:min-h-11">
            {a.button}
            <DropdownMenuShortcut aria-hidden="true">{KEY_OF[a.kind]}</DropdownMenuShortcut>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function QuickActionDialog({ kind, onClose }: { kind: QuickActionKind; onClose: () => void }) {
  const action = ACTIONS.find((a) => a.kind === kind)!
  const client = useApi()
  const invalidate = useInvalidate()
  const toast = useToast()
  const today = useToday()

  const projects = useQuery(useCallback(() => client.listProjects(), [client]))
  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const [project, setProject] = useState<string | null>(null)
  const [priority, setPriority] = useState<Priority>('medium')
  const [due, setDue] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // No project is chosen for the person: the default is an explicit "No project".
  const selectedProject = project ?? NO_PROJECT

  const isText = kind === 'capture' || kind === 'followup'
  const standupPath = `01-Daily/${today.slice(0, 4)}/${today}.md`
  const target =
    kind === 'capture'
      ? 'Writes a capture note to 00-Inbox/'
      : kind === 'followup'
        ? `Appends a line under Follow-ups in ${standupPath}`
        : `Writes ${FOLDER[kind]}${title.trim() || '<title>'}.md`
  const disabled = busy || (isText ? !text.trim() : !title.trim())

  // `wrote` is called after each write that succeeded, so a later failure
  // (the second call of a follow-up) still refreshes what is on screen.
  async function run(wrote: () => void): Promise<string> {
    if (kind === 'capture') {
      const note = await client.createCapture({ text: text.trim() })
      wrote()
      return `Saved capture as ${note.path}`
    }
    if (kind === 'followup') {
      const line = text.trim()
      const standup = await client.getStandupToday()
      // A missing note is created, and an untouched one filled, with carry-forward before the line goes in.
      let note = standup.exists ? standup.note : null
      const started = !standup.exists || standup.untouched
      if (!note || started) {
        note = (await client.startStandup()).note
        wrote()
      }
      await client.appendToStandup({ section: 'Follow-ups', text: line, expected_hash: note.content_hash })
      wrote()
      const lead = !standup.exists
        ? `Created ${note.path} from the daily template, then appended`
        : started
          ? `Filled ${note.path} with carry-forward, then appended`
          : 'Appended'
      return `${lead} "${line}" under Follow-ups in ${note.path}`
    }
    const note = await client.createNote({
      type: kind,
      title: title.trim(),
      project: selectedProject !== NO_PROJECT ? selectedProject : undefined,
      ...(kind === 'task' ? { priority, due: due || undefined } : {}),
    })
    wrote()
    return `Created ${note.path} from the ${kind} template`
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (disabled) return
    setBusy(true)
    setError('')
    let anyWrite = false
    try {
      const message = await run(() => {
        anyWrite = true
      })
      toast.show(message)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The request failed.')
      setBusy(false)
    } finally {
      if (anyWrite) invalidate()
    }
  }

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent showCloseButton={false}>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <DialogHeader>
            <DialogTitle className="text-panel font-bold">{action.title}</DialogTitle>
            <DialogDescription className="sr-only">Creates a Markdown note in the vault.</DialogDescription>
          </DialogHeader>

          {kind === 'capture' && (
            <Field label="Thought" htmlFor="qa-text">
              <Textarea id="qa-text" rows={4} value={text} onChange={(e) => setText(e.target.value)} placeholder="Anything. It lands in 00-Inbox and is sorted at triage." autoFocus />
            </Field>
          )}
          {kind === 'followup' && (
            <Field label="Follow-up" htmlFor="qa-text">
              <Input id="qa-text" value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask infra for the staging database refresh date" autoFocus />
            </Field>
          )}
          {!isText && (
            <>
              <Field label="Title (becomes the file name)" htmlFor="qa-title">
                <Input id="qa-title" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
              </Field>
              <Field label="Project" htmlFor="qa-project">
                <Select value={selectedProject} onValueChange={setProject}>
                  <SelectTrigger id="qa-project" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_PROJECT}>No project</SelectItem>
                    {projects.status === 'success' &&
                      projects.data.map((p) => (
                        <SelectItem key={p.slug} value={p.slug}>
                          {p.title}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </Field>
            </>
          )}
          {kind === 'task' && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="Priority" htmlFor="qa-priority">
                <Select value={priority} onValueChange={(v) => setPriority(v as Priority)}>
                  <SelectTrigger id="qa-priority" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="high">high</SelectItem>
                    <SelectItem value="medium">medium</SelectItem>
                    <SelectItem value="low">low</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Due" htmlFor="qa-due">
                <Input id="qa-due" type="date" value={due} onChange={(e) => setDue(e.target.value)} />
              </Field>
            </div>
          )}

          {error && (
            <p role="alert" className="m-0 font-medium text-status-blocked">
              {error}
            </p>
          )}
          <p id="qa-target" className="mono m-0 text-muted-ink">
            {target}
          </p>
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={disabled}>
              {busy ? 'Saving' : action.submit}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={htmlFor} className="text-small font-semibold text-muted-ink">
        {label}
      </Label>
      {children}
    </div>
  )
}

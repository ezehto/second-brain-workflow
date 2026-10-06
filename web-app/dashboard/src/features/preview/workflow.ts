import type { FailureKind, LoopEntry, PreviewWorkflowItem } from '@/preview'
import type { StatusTone } from '@/domain/status'

export const STAGE_SHORT = ['Understand', 'Plan', 'Implement', 'Test', 'Review', 'Complete']
export const STAGE_HINT = [
  'Requirements clear? If not, stop and ask.',
  'Approach agreed, approval if needed.',
  'The plan is valid; build and fix locally.',
  'Failures are classified before any fix.',
  'Must Fix findings go back, by cause.',
  'Done only with evidence and no open Must Fix.',
]

export interface Cause {
  label: string
  code: string
  key: string
  /** The stage an item returns to after a failure of this kind. */
  dest: number
  action: string
  rule: string
}

export const CAUSES: Record<FailureKind, Cause> = {
  impl: {
    label: 'Implementation issue',
    code: 'IMPLEMENTATION_FAILURE',
    key: 'implementation-failure',
    dest: 2,
    action: 'Fix the implementation, then run the tests again.',
    rule: 'The plan is still valid and the problem is local. Fix the implementation and test again; do not restart planning.',
  },
  plan: {
    label: 'Design issue',
    code: 'PLAN_FAILURE',
    key: 'plan-failure',
    dest: 1,
    action: 'Update the plan, record the decision, then implement.',
    rule: 'The approach is invalid. Revisit requirements, constraints and options, update the plan, then implement. Do not keep patching.',
  },
  req: {
    label: 'Requirement issue',
    code: 'REQUIREMENT_FAILURE',
    key: 'requirement-failure',
    dest: 0,
    action: 'Clarify the requirement with its owner, then replan.',
    rule: 'The requirement is unclear or in conflict. Stop and ask, clarify, then replan and implement.',
  },
}

export const CAUSE_ORDER: FailureKind[] = ['impl', 'plan', 'req']

/** Two failures of one kind warn; three stop the loop and send the item to planning. */
export const WARN_AT = 2
export const STOP_AT = 3

/** Status word of an item: blocked wins, else the stage maps to the task vocabulary. */
export function statusOf(item: PreviewWorkflowItem): string {
  if (item.blocked) return 'blocked'
  return ['planned', 'planned', 'in-progress', 'in-progress', 'review', 'done'][item.stage]
}

export const statusTone = (item: PreviewWorkflowItem): StatusTone =>
  item.blocked ? 'blocked' : (['neutral', 'neutral', 'progress', 'progress', 'review', 'done'] as const)[item.stage]

export interface Derived {
  rework: number
  /** The last history entry is a stage move straight after a failure. */
  sentBack: boolean
  lastFail: Extract<LoopEntry, { kind: 'fail' }> | null
  /** The highest count of failures of one kind. */
  sameMax: number
  sameCause: FailureKind | null
  warned: boolean
  stopped: boolean
  previous: string
  next: string
  failWord: string
  failNote: string
}

export function derive(item: PreviewWorkflowItem, stageNames: string[]): Derived {
  const h = item.history
  const fails = h.filter((e): e is Extract<LoopEntry, { kind: 'fail' }> => e.kind === 'fail')
  const last = h[h.length - 1]
  const before = h[h.length - 2]
  const sentBack = !!before && before.kind === 'fail' && last.kind === 'stage'
  const lastFail = fails.at(-1) ?? null
  const counts: Partial<Record<FailureKind, number>> = {}
  fails.forEach((e) => (counts[e.cause] = (counts[e.cause] ?? 0) + 1))
  const sameMax = Math.max(0, ...Object.values(counts))
  const entries = h.filter((e) => e.kind === 'stage')
  return {
    rework: fails.length,
    sentBack,
    lastFail,
    sameMax,
    sameCause: lastFail?.cause ?? null,
    warned: sameMax === WARN_AT,
    stopped: sameMax >= STOP_AT,
    previous: entries.length > 1 ? stageNames[entries[entries.length - 2].stage] : 'N/A',
    next: item.stage < 5 ? stageNames[item.stage + 1] : 'N/A',
    failWord: sentBack && lastFail ? `${lastFail.source}, ${CAUSES[lastFail.cause].label.toLowerCase()}` : '',
    failNote: sentBack && lastFail ? lastFail.note : '',
  }
}

export type ActionMode = 'test' | 'review' | 'back'

export interface ActionInput {
  mode: ActionMode
  result: 'pass' | 'fail'
  cause: FailureKind | ''
  note: string
}

export const taskPath = (item: PreviewWorkflowItem) => `02-Work/Tasks/${item.title}.md`

/** Which modes the item's stage allows. */
export function allowedModes(item: PreviewWorkflowItem): Record<ActionMode, boolean> {
  return {
    test: item.stage === 2 || item.stage === 3,
    review: item.stage === 4,
    back: item.stage >= 1 && item.stage < 5,
  }
}

/** A send-back must land behind the current stage. Returns a reason when the input is not valid. */
export function validate(item: PreviewWorkflowItem, input: ActionInput): string | null {
  const needsCause = input.mode === 'back' || input.result === 'fail'
  if (!needsCause) return null
  if (!input.cause) return 'Pick the cause. It decides which stage the item returns to.'
  if (input.mode === 'back' && CAUSES[input.cause].dest >= item.stage) return 'That cause does not return the item to an earlier stage. Pick another.'
  return null
}

/** Applies a recorded result to an item, returning the new item and the toast naming the file. */
export function applyAction(
  item: PreviewWorkflowItem,
  input: ActionInput,
  date: string,
  stageNames: string[],
): { item: PreviewWorkflowItem; message: string } {
  const history = [...item.history]
  const path = taskPath(item)
  const note = input.note.trim()
  let { stage, owner, action } = item
  let message: string
  const passed = input.mode !== 'back' && input.result === 'pass'

  if (passed && input.mode === 'test') {
    if (stage < 3) history.push({ kind: 'stage', stage: 3, date })
    history.push({ kind: 'pass', stage: 3, date, note })
    history.push({ kind: 'stage', stage: 4, date })
    stage = 4
    owner = 'Reviewer'
    action = 'Review the change against the review checklist.'
    message = `Updated ${path}: stage review, status review. Tests recorded as passed.`
  } else if (passed) {
    history.push({ kind: 'pass', stage: 4, date, note })
    owner = 'You'
    action = 'Mark complete, with evidence.'
    message = `Updated ${path}: review recorded as passed. Stage stays review.`
  } else {
    const cause = CAUSES[input.cause as FailureKind]
    const failStage = input.mode === 'test' ? 3 : input.mode === 'review' ? 4 : item.stage
    if (input.mode === 'test' && stage < 3) history.push({ kind: 'stage', stage: 3, date })
    const source = input.mode === 'test' ? 'Test failed' : input.mode === 'review' ? 'Review failed' : 'Sent back'
    const stop = history.filter((e) => e.kind === 'fail' && e.cause === input.cause).length + 1 >= STOP_AT
    const dest = stop ? 1 : cause.dest
    history.push({ kind: 'fail', stage: failStage, date, cause: input.cause as FailureKind, source, note: note || 'No detail recorded.' })
    history.push({ kind: 'stage', stage: dest, date })
    stage = dest
    owner = 'You'
    action = stop
      ? 'Stop patching. Analyse the root cause, review assumptions and requirements, then replan.'
      : dest === 2
        ? CAUSES.impl.action
        : dest === 1
          ? CAUSES.plan.action
          : CAUSES.req.action
    const rework = history.filter((e) => e.kind === 'fail').length
    message = `Updated ${path}: stage ${stageNames[stage].toLowerCase()}, rework ${rework}, failure ${cause.key}.${stop ? ' Third failure of the same kind: the stop rule sent it to planning.' : ''}`
  }
  return { item: { ...item, stage, owner, action, history }, message }
}

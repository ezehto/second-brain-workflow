import { describe, expectTypeOf, it } from 'vitest'
import type { ApiClient } from './client'
import type { components, operations } from './generated/schema'
import { INDEX_PROBLEM_CATEGORIES, STANDUP_SECTIONS, type CreateNoteRequest, type IndexProblemCategory, type NoteListParams, type Paginated, type StandupSection } from './types'

type Schemas = components['schemas']
type Result<K extends keyof ApiClient> = ApiClient[K] extends (...args: never[]) => Promise<infer R> ? R : never

// Compile-time: the client's results are the contract's schemas. A change to openapi.yaml that
// regenerates schema.d.ts and moves a shape breaks the build here, not in a page at runtime.
describe('ApiClient types come from the generated contract', () => {
  it('results are the generated schemas', () => {
    expectTypeOf<Result<'me'>>().toEqualTypeOf<Schemas['Me']>()
    expectTypeOf<Result<'login'>>().toEqualTypeOf<Schemas['Me']>()
    expectTypeOf<Result<'getDashboard'>>().toEqualTypeOf<Schemas['Dashboard']>()
    expectTypeOf<Result<'getIndexStatus'>>().toEqualTypeOf<Schemas['IndexStatus']>()
    expectTypeOf<Result<'search'>>().toEqualTypeOf<Schemas['SearchResponse']>()
    expectTypeOf<Result<'getStandupToday'>>().toEqualTypeOf<Schemas['StandupToday']>()
    expectTypeOf<Result<'startStandup'>>().toEqualTypeOf<Schemas['StartStandupResponse']>()
    expectTypeOf<Result<'appendToStandup'>>().toEqualTypeOf<Schemas['AppendStandupResponse']>()
    expectTypeOf<Result<'getProject'>>().toEqualTypeOf<Schemas['ProjectDetail']>()
    expectTypeOf<Result<'listProjects'>>().toEqualTypeOf<Schemas['ProjectSummary'][]>()
    expectTypeOf<Result<'lookupNote'>>().toEqualTypeOf<Schemas['NoteDetail']>()
    expectTypeOf<Result<'createNote'>>().toEqualTypeOf<Schemas['NoteSummary']>()
    expectTypeOf<Result<'createCapture'>>().toEqualTypeOf<Schemas['NoteSummary']>()
    expectTypeOf<Result<'triageCapture'>>().toEqualTypeOf<Schemas['TriageResponse']>()
  })

  it('the narrowed create request is accepted by the contract', () => {
    expectTypeOf<CreateNoteRequest>().toExtend<Schemas['CreateNoteRequest']>()
  })

  it('the constant lists cover every member of the contract enums', () => {
    expectTypeOf<(typeof INDEX_PROBLEM_CATEGORIES)[number]>().toEqualTypeOf<IndexProblemCategory>()
    expectTypeOf<(typeof STANDUP_SECTIONS)[number]>().toEqualTypeOf<StandupSection>()
    expectTypeOf<StandupSection>().toEqualTypeOf<Schemas['SectionEnum']>()
  })

  it('the notes list params are accepted by the contract', () => {
    expectTypeOf<NoteListParams>().toExtend<NonNullable<operations['notes_list']['parameters']['query']>>()
  })

  it('a page of notes has the contract fields', () => {
    expectTypeOf<Paginated<unknown>['count']>().toEqualTypeOf<Schemas['PaginatedNoteSummaryList']['count']>()
  })

  it('response nullability: priority is free text, today is a date string', () => {
    expectTypeOf<Schemas['NoteSummary']['priority']>().toEqualTypeOf<string | null>()
    expectTypeOf<Schemas['Dashboard']['today']>().toEqualTypeOf<string>()
  })
})

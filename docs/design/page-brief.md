# Page-builder brief (frontend work packages)

Shared instructions for every agent building a page of the dashboard. Read
this, then your package's own instructions.

## Contents

- [Read first](#read-first)
- [Rules](#rules)
- [Data](#data)
- [Shared components](#shared-components)
- [Routing](#routing)
- [Tests and checks](#tests-and-checks)
- [Report](#report)

## Read first

1. `docs/design/app-request.md` and `docs/design/dashboard-request.md`: what
   the user wants, in their words. Your page must answer its daily-use
   questions first.
2. `docs/design/2026-10-06-ux-assessment.md`: sections 5.2 (layout and
   density, with exact px), 5.3 (colour), 5.5 (your page's layout and the
   questions it answers), 5.6 (responsive), 5.7 (components), 8 (metrics and
   charts stay) and 9 (decisions).
3. `docs/design/prototype/<Your>.dc.html`: the approved prototype of your
   screen, for structure, copy and sample data; do not port its format.
4. The app: `web-app/dashboard/src/`. Read `components/` (all shared
   primitives), `api/types.ts`, `api/client.ts`, `api/useQuery.ts`,
   `api/listAll.ts`, `lib/routes.ts`, `lib/clock.tsx`, `lib/dates.ts`,
   `domain/`, `preview/index.ts`, `test/helpers.tsx`, and
   `features/dashboard/` as the worked example of a page.
5. `docs/plan/phase-1-foundation.md` sections 2.3 (status vocabularies), 5
   (API surface) and your page's P1-3x task entry (tests it names).

Invoke the `frontend-design:frontend-design` skill before building, and the
`dataviz` skill before any chart. Check library APIs through context7, not
memory.

## Rules

- Work only in your package's folder under `src/features/<name>/`, plus new
  test files beside it. Do not edit `routes.tsx`, `nav.ts`, `AppShell`,
  `Rail`, `Header`, `QuickActions`, `index.css`, shared components, or another
  package's folder. If a shared component needs a change, make a minimal
  additive change and name it in your report; never change its existing
  behaviour.
- Density and type: the assessment's 5.2 targets. Rows 36px (one line) or
  48px (two lines) through `CardRow`/`TaskRow`; dense tables 32px; body 14px;
  nothing readable under 13px; spacing only 4/8/12/16/24/32; weights 400 to
  700. Use the `.t-*` type classes and token utilities, never raw hex.
- Colour: accent is interaction only. Status through `StatusChip` and
  `PriorityMark`. Preview data gets `PreviewBadge`, never a plain caption.
- No filled accent card. Panels are `Card`/`CardHead`/`CardRow`; inside a
  panel everything is ruled rows on one surface, no nested tiles.
- Every chart answers a question stated in its heading, shows its numbers as
  text, uses status hues, and is at most 160px tall on the Dashboard (taller
  is fine on a page that is about that chart).
- Real buttons and links, labels on inputs, visible focus, colour never the
  only signal. Sentence case, no all-caps, no emoji.
- Status changes go through `StatusMenu`. Writes name the Markdown file in the
  toast. `N/A` for missing values, `Estimated` where the data is an estimate.
- Loading, empty and error states for every data-backed section through
  `QueryBoundary`; empty states say what to do next.
- Responsive: usable at 390 wide, designed for 1440 and 1920. Tables wider
  than the screen become two-line rows on phones.
- Do not start or stop the dev server on port 5173 (it belongs to the user).
  Do not commit.

## Data

- Phase 1 data comes from `useApi()` (the mock client in this build). Never
  import fixtures directly in a page. Use `useQuery` with a `useCallback`
  fetcher; `listAllNotes` for lists that may exceed a page.
- Later-phase data lives only in `src/preview/index.ts` and is shown with
  `PreviewBadge`. If your page needs preview data that is not there, add it
  to that file under a new exported block with a `source` string; do not
  invent precision the described data could not produce.
- The project context filter is the `project` query parameter (decision 2):
  read it with the router and filter your page's data by it.
- "Today" comes from `useToday()`; never `new Date()`.

## Shared components

In `src/components/`: `Card`, `CardHead` (title, `count` slot), `CardRow`
(`lines` 1 or 2), `CardFootnote`, `InsetItem` (forms only), `StatTile`
(`compact`), `StatusChip`, `PriorityMark`, `PreviewBadge`, `TaskRow`,
`StatusMenu`, `Segmented`, `ProgressBar`, `Donut`, `ActivityList`,
`EmptyState`, `ErrorState`, `LoadingRows`, `QueryBoundary`, `Icon`,
`ToastProvider`/`useToast`, and the shadcn `ui/` primitives (button, input,
select, dialog, tabs, tooltip, dropdown-menu, label, textarea).

## Routing

Export your page component(s) from `src/features/<name>/index.ts`. The
orchestrator wires routes in `routes.tsx` after merge. Use the helpers in
`lib/routes.ts` for every link (`routes`, `noteHref`, `projectHref`,
`tasksHref`) and the documented Tasks URL contract, and get every internal
link through `useProjectHref()` in `lib/projectContext.ts` (`href.note`,
`href.project`, `href.tasks`, `href.link`) so the project context filter
survives navigation. Pages get their title and
subtitle through the route `handle`; tell the orchestrator the values you
want.

## Tests and checks

Write tests with the code: rendering from a fixture, loading, empty and error
states, the page's own rules, filters mapping to query parameters, and each
write path (success, 409, 422 where the API defines them). Use
`src/test/helpers.tsx`. Run `npm run lint`, `npm run typecheck`,
`npm run test -- --run` and `npm run build` in `web-app/dashboard/`. Screenshot
your page at 1440 and 390 with the cached Chromium
(`/tmp/pw/node_modules/playwright-core`, executable under
`~/.cache/ms-playwright/chromium-1217/*/chrome`, `--no-sandbox`) against the
running dev server at `http://127.0.0.1:5173` once your route is wired; until
then render it in a test or a temporary local route you remove before
reporting.

## Report

Status; files; the exact tail line of each command; the route components and
`handle` values to wire; any additive change to a shared component; what you
left out and why; data the page needs that the plan does not provide.

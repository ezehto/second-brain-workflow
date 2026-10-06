# Second Brain web app: UX assessment and proposal

Assessment only. No code was changed. Written 2026-10-06 against the running dashboard
(`web-app/dashboard/`, dev server on 127.0.0.1:5173, mock API, so the data is sample data) and
the request in `docs/design/app-request.md`.

## Contents

- [1. Summary](#1-summary)
- [2. What exists](#2-what-exists)
- [3. Measurements](#3-measurements)
- [4. Assessment](#4-assessment)
- [5. Proposal](#5-proposal)
  - [5.1 Information architecture](#51-information-architecture)
  - [5.2 Layout principles](#52-layout-principles)
  - [5.3 Colour](#53-colour)
  - [5.4 Dashboard redesign](#54-dashboard-redesign)
  - [5.5 The other pages](#55-the-other-pages)
  - [5.6 Responsive plan](#56-responsive-plan)
  - [5.7 Components](#57-components)
- [6. Work packages](#6-work-packages)
- [7. Open questions for the user](#7-open-questions-for-the-user)
- [8. Addendum: metrics and charts stay](#8-addendum-metrics-and-charts-stay-user-instruction-2026-10-06)
- [9. Decisions](#9-decisions-user-go-ahead-2026-10-06)

## 1. Summary

The app is a competent, accessible, well-tested shell with one real page, and it is a good base: tokens,
status vocabulary, API client and mock layer, shadcn primitives and the Today's focus rule all stay.
The Dashboard, however, is a showcase and not yet a daily tool. It repeats the same tasks up to four
times, spends 29% of its card area on sample data for later phases, wastes the top 250px (and on
mobile 800px) before the first useful row, and cannot change a task's status. The three changes with
the most effect:

1. **Collapse the 136px two-row header and the five stat tiles into a 52px top bar and a one-line status strip**, so "what should I work on" starts at about y=110 instead of y=250 (y=804 on a phone).
2. **Rebuild Dashboard around the daily questions, not around data sources**: one Focus list with inline status change, a Blocked and Decisions panel that never repeats Focus, the standup writable in place, and "Done recently". Drop the donut, workflow tiles, Claude usage and Integrations from this page.
3. **Use the width and tighten the scale**: 3 columns at 1920 (content currently stops at x=1572, 348px dead on the right), 52px/36px/48px chrome and row heights, 14px body, no 12px reading text, and retire the filled violet card so colour means status only.

## 2. What exists

| Area | Fact | Where |
|---|---|---|
| Pages | Only Dashboard is real. 13 other routes render `NotBuiltPage` ("Not built yet"), including Tasks, Projects, Standup, Inbox, Search, note reader | `src/routes.tsx`, `features/placeholder/` |
| Dashboard | 10 sections: stat tiles (5), Today's focus, Tasks by status, Needs attention, Active projects, Meetings (preview), Today's standup, Workflow stages (preview), Recent activity, How you are improving (preview), Integrations (preview) | `features/dashboard/*` |
| Navigation | Fixed 240px left rail, 4 groups, 12 items, 3 tagged "Preview", count chips on Inbox and Index status. Below 832px (`rail` breakpoint) it becomes a hamburger drawer | `components/Rail.tsx`, `nav.ts`, `AppShell.tsx` |
| Header | Two rows: title and subtitle, search, context segmented control (All projects plus each active project), index pill, avatar; then five quick-action buttons and Start standup | `components/Header.tsx` |
| Quick actions | Task, Follow-up, Decision, Note, Capture; each opens a dialog and writes through the API | `components/QuickActions.tsx` |
| Tokens | Dark only. Ground `#0F0F14`, card `#1B1B24`, accent `#9B8CFF`, fill `#6B58E6`, status hues (progress, blocked, risk, done, review, planned). Radius 16/12/10 | `src/index.css`, `docs/design/theme.md` |
| Type | Plus Jakarta Sans Variable (UI), DM Mono (paths, times). Body 14px, notes 12px, h2 16px, page title 24px (34px clamp on the day title), weights up to 800 | `src/index.css` |
| Primitives | shadcn button, dialog, input, label, select, tabs, textarea, tooltip; own Card, CardHead, CardRow, InsetItem, AccentCard, StatTile, StatusChip, ProgressBar, Donut, Segmented, ActivityList, Toast, EmptyState, ErrorState, QueryBoundary | `components/`, `components/ui/` |
| Data layer | `ApiClient` interface with HTTP and mock implementations, `useQuery`, `listAllNotes`, domain rules (focus, attention, health, standup) with unit tests. `changeStatus` exists on the client but no UI calls it | `src/api/`, `src/domain/` |
| Preview data | Meetings, workflow stages, learning, Claude usage, integrations, labelled "Sample data" with phase | `src/preview/index.ts` |
| Layout | `main` is `max-w-[1360px]`, padded 28px; cards `gap-5` (20px) | `AppShell.tsx` |
| Responsive | Fluid grids (`auto-fit minmax`), rail drawer, stacked on phones; no horizontal overflow at any tested width | measured below |
| Tests | Section tests, quick action tests, domain tests, mock client tests | `*.test.ts(x)` |

## 3. Measurements

Headless Chromium, mock data, Dashboard route. Request column is what `app-request.md` asks for.

| Measure | 1920x1080 | 1440x900 | 1024x768 | 390x844 | Request |
|---|---|---|---|---|---|
| Content width (x range) | 1304px, x 268 to 1572 | 1144px, x 268 to 1412 | 728px | 358px | "Use the available screen space"; "wide screens" |
| Share of viewport used by content | 68% (right margin 348px dead, 18%) | 79% | 71% | 92% | Avoid large empty space |
| Rail | 240px (12.5%) | 240px (16.7%) | 240px (23%) | drawer | Side navigation |
| Header height before content | 136px (12.6% of viewport) | 136px | 191px | 428px (51% of viewport) | Minimal chrome |
| First task row appears at | y=250 | y=250 | y=403 | y=804 (below the fold) | "Immediately know what to work on" |
| Page height | 2183 (2.0 screens) | 2204 (2.4) | 3453 (4.5) | 5174 (6.1) | High density |
| Columns | 2 then 2 then 3 | same | 1 then 2 | 1 | Multi-column desktop |
| Horizontal overflow | none | none | none | none | Pass |

| Type (measured on `main` text) | Value | Request |
|---|---|---|
| Largest headings | h1 34px (day title, clamp 24 to 34), stat values 26px, other numbers 24px and 20px | "Huge headings" to avoid. 34px plus weight 800 is the largest thing on the page and it is a date |
| Section headings | 16px x10 | Fine |
| Body | 14px x52 text nodes | Fine |
| Secondary | 13px x59 nodes | Fine for secondary |
| Captions | 12px x48 nodes (notes, mono timestamps, footnotes, group labels) | 25% of all text is 12px; several carry meaning (due dates, blocked reasons, rules) |

| Density and cards | Figure |
|---|---|
| Bordered boxes on the Dashboard | 10 section cards, 5 stat tiles, 6 workflow tiles, 2 inset tiles: **23** |
| Card chrome | Head padding 16 top and 12 bottom, 20 sides, 20px gap between cards: about 48px of pure padding and gap per card, roughly 480px or 22% of page height |
| Row height | Two-line focus and attention rows 64.5px, project rows about 90px; single-line rows 32 to 44px |
| Repetition | "Confirm rate limit with SMS provider" appears 4 times above the fold (Focus, Blocked, Overdue, High priority); "Rotate staging API credentials" 3 times. Blocked count 2 appears in the tile, the donut, Needs attention, two project badges and Focus chips |
| Sample data | Meetings 189px, Workflow 191, Improving 333, Integrations 258 = 971px, **29%** of summed card height, 4 of 10 sections |
| Empty pockets at 1920 | below Needs attention about 130px, below Improving 150px, below Integrations 225px, beside Meetings and Standup 107px, from `items-start` columns of unequal height |
| Control height | 40px buttons and inputs on desktop, 44px on phone. Comfortable, but 5 quick actions plus Start standup plus index pill consume a full row |

## 4. Assessment

Tied to the request's daily questions: what to work on, what is blocked, what did I accomplish, what to improve.

### Working well

- **Today's focus rule** (overdue, then blocked, then due today, then in review; at most 5; rule stated in a footnote). It directly answers "what should I work on" and is explainable, not a score. `domain/focus.ts` stays.
- **Honest data labelling**: `N/A`, "Estimated", "Sample data, Phase 4" on every preview section. Matches the honesty rules and prevents a fake command center.
- **Status always has a word and a dot**, not colour alone. Accessible and scannable.
- **Project health from a stated rule** (blocked, at risk, on track) rather than a percentage.
- **Quick actions exist** and write to the vault: capture, task, decision, lesson, follow-up. "Fast access to frequently used actions" is met in function.
- **Context switcher concept** (All projects vs one project) is the right global-to-project pivot for the request's two views.
- **Stack discipline**: typed `ApiClient` with mock, URL contract for task filters (`tasksHref`), domain logic separated and tested, reduced-motion respected, no horizontal overflow.
- **Dark theme with muted status hues** is easy on the eyes and matches the approved prototype.

### Difficult to use

- **Nothing is actionable on the Dashboard.** Task rows show status chips but cannot change status or record progress, although `changeStatus` exists. "Easy to update status" fails; every update means leaving the page, and the destination pages do not exist yet.
- **Same task shown 3 to 4 times** (Focus, Blocked, Overdue, High priority groups). It inflates scanning cost and makes "what is blocked" look larger than it is.
- **Needs attention is a wall of text rows**: 24px counts, group headings, then 13px names with 12px grey reasons run together on one line ("... blocked: Waiting on the provider account manager"). The reason, the actual decision input, is the weakest-contrast text.
- **Filled violet Today's focus card** is the loudest thing on the page, and red or blue status chips sit on violet, a poor contrast pair. Colour here is decoration, against "colors communicate status".
- **Two-row header (136px)** repeats navigation affordances (search, context, index, avatar, five buttons, Start standup). On a phone it is 428px: the first task is below the fold, which contradicts "mobile should prioritise Today's tasks".
- **Tasks by status donut** answers a question nobody asks daily (14 tasks including done and cancelled) and takes 251px.
- **Section titles and 12px captions** carry rules and sources everywhere; rule footnotes are always visible and add 40px to 60px to each card.
- **Rail items tagged "Preview"** (3 of 12) read as broken navigation; the Preview chip sits where count chips go.
- **Dead links**: every nav item except Dashboard leads to "Not built yet", including every "Open ..." button in the cards.

### Missing

- **Pending decisions** (decision notes with status `proposed`). The request's first purpose is "help me decide" and Phase 1 data supports it. Not shown anywhere.
- **What I accomplished**: Recent activity lists file modifications ("13:05 project, vault IPP"), not completed work. No "done recently" with evidence.
- **Follow-ups**: a quick action exists, but no place shows open follow-ups, so recording one gives no way to see it again.
- **Standup in place**: only a status line ("Not started, 5 tasks and 2 blockers would be carried forward") and an Open button. DSU recording is "very easy" only if it can be written from here (append endpoint exists).
- **Priority is only a word** inside a group heading; no visible priority marker on rows.
- **Look-back**: DSU history, carry-over, recurring blockers. Not on any page yet.
- **Project view and global task view**: neither exists. Project rows have no progress beyond "1 of 4 done".
- **Keyboard path**: no command palette or shortcuts for the five capture actions.
- **Time of the last pass and "stale"**: index state is visible, but not "this task has not moved in N days".

### Can be simplified

- **Header**: merge title and search and context into one 52px bar; the five buttons become one "New" menu plus keys; the index pill shows only when there are problems.
- **Stat tiles (5 boxes with icon chips)** become one status strip; the numbers duplicate Needs attention.
- **Needs attention** becomes "Blocked" plus "Decisions to make", excluding anything already in Focus.
- **Active projects**: three lines per row plus a progress bar become one ruled row per project.
- **Rule footnotes** move behind an info tooltip; the rule stays one click away.
- **Standup and Meetings panels** merge into one "Today" panel.
- **Section chrome** (CardHead note plus action plus footnote) loses the always-visible source text for real data; keeps it for preview data only.

### Should be redesigned

- **Dashboard composition** (section 5.4): from a 10-card showcase to six working panels and a strip, answering the questions in the request's own order.
- **Colour roles**: accent for interaction, status hues for state, no filled accent card.
- **Type and spacing scale**: smaller title, no 12px reading text, tighter rows (section 5.2).
- **Rail**: collapsible to icons below 1280px, "Later" group for previews.
- **Mobile first screen**: top bar plus status strip plus Focus list, and a bottom tab bar.
- **Task row** as the shared unit across Dashboard, Tasks, Project and Search, with inline status and priority.

### Should remain unchanged

- Tokens' palette and the Plus Jakarta Sans plus DM Mono pairing (readable, already loaded; mono stays for paths only).
- `ApiClient`, mock client, `useQuery`, `listAllNotes`, domain modules and their tests.
- Status vocabularies and `StatusChip` semantics; the Today's focus rule; project health rule.
- `tasksHref`, `noteHref`, `projectHref` URL contract; `QuickActionDialog` forms and their API calls (the entry point changes, not the dialogs).
- Honest labelling of preview data (`src/preview/index.ts` contract).
- Sample-data note in the rail; focus ring; reduced-motion CSS; sr-only count text; Dialog drawer behaviour.

## 5. Proposal

### 5.1 Information architecture

Keep the four rail groups and 12 destinations; no new top-level routes. What changes is order of emphasis and what each page answers first.

| Page | Answers first | Notes |
|---|---|---|
| Today (Dashboard `/`) | What do I work on next, what is blocked, what must I decide, what did I finish | Global view; context switcher filters every panel |
| Tasks | What is open across all projects, grouped, sorted by priority and due | The global workload view; note reader beside it |
| Projects, `/projects/:slug` | What is the state of this one project, in one page | Project view with tabs; see 5.5 |
| Standup | What did I do, what will I do, what blocks me; what repeats across days | Write-in-place plus history |
| Inbox | What did I capture that needs sorting | Triage actions inline |
| Knowledge, Decisions | What did we decide or learn about X | One list pattern, two filters |
| Search | Where is the thing I half remember | Also a Ctrl+K palette |
| Index status | Can I trust what I am seeing | Counts and problems |
| Workflow, Timeline, Upskilling | Preview only until their phases | Stay under a quiet "Later" group |

Navigation: rail groups become Today (Today, Standup, Inbox), Work (Tasks, Projects), Knowledge (Knowledge, Decisions, Search), System (Index status), and a collapsed "Later" group (Workflow, Timeline, Upskilling) so previews stop looking like broken items. Rail shows 224px at 1280 and up, a 56px icon rail from 832 to 1279, and is replaced by a bottom tab bar below 640 (Today, Tasks, Standup, Projects, More) with a floating "+" for capture. Counts stay on Inbox, Tasks (blocked) and Index status (problems only).

### 5.2 Layout principles

- **The page is a workspace, not a webpage.** Content max width 1840px, centred only above that. The note reader keeps a 72ch measure inside its own pane.
- **Columns by width:**

| Viewport | Rail | Columns | Dashboard arrangement |
|---|---|---|---|
| 1920 | 224px | **3** (5/12, 4/12, 3/12) | Focus and Done recently; Blocked, Decisions, Projects; Standup/Today, Learning |
| 1440 | 224px | **2** (7/12, 5/12) | Focus, Projects on the left; Blocked, Decisions, Standup on the right |
| 1024 | 56px icons | **2** (8/12, 4/12) with the side column dropping under at 900 | As 1440, tighter |
| 768 | 56px icons | 1, small panels 2-up | Strip, Focus, then pairs |
| 390 | bottom tabs | 1, priority order | Section 5.6 |

- **Density targets** (current values in brackets):

| Item | Target | Now |
|---|---|---|
| Top bar | 52px | 136px |
| Single-line row | 36px | 32 to 44 |
| Two-line row (title plus reason) | 48px | 64.5 |
| Dense table row (Tasks) | 32px, toggle | n/a |
| Panel padding | 12px sides, header 40px | 20px sides, header 60px |
| Panel gap, page gutter | 16px, 24px (16px on phone) | 20px, 28px |
| Controls | 32px desktop, 44px touch | 40px |
| Panel radius, control radius | 12px, 8px | 16px, 10px |

- **Type scale (px, line height):** 12/16 caption (timestamps, counts only), 13/18 secondary, **14/20 body and row titles**, 16/22 panel titles (600), 20/26 page title (700), 28/34 the date on Today only (700), 22/26 tabular figures in the status strip. Weights 400, 500, 600, 700; drop 800. Letter spacing only on the 28 and 20. Nothing readable below 13px; 12px must hold at least 4.5:1 (the `faint` token `#7D7D90` on rail and card is borderline and should be checked or lightened).
- **Spacing scale (px):** 4, 8, 12, 16, 24, 32. Nothing else.
- **Cards versus rows.** A bordered panel is kept only for a group the user scans as a unit: Focus, Blocked, Decisions, Projects, Standup, Done recently. Inside a panel everything is ruled rows on one surface; no nested tiles (kills InsetItem on the Dashboard and the six stage tiles). Counts and filters are a strip or a segmented control, never five boxes. Tables for Tasks and Projects.
- **Grouping.** Panels are ordered by the request's flow: understand (strip), decide (Blocked, Decisions), prioritise and execute (Focus, Projects), record (Standup), remember and improve (Done recently, Learning). Panel titles carry a count, not a subtitle.
- **Equal-height rows** (`align-items: stretch`, inner scroll after about 8 rows) so columns end together; no `items-start` pockets.

### 5.3 Colour

- **Accent violet is for interaction only**: current nav item, primary button, links, focus ring, selected tab. It is never a status and never a fill behind content.
- **Status hues are the only other colour** and keep their present values: blocked, overdue and failed red `#FF7D73`; at risk, due today amber `#F5B85C`; in progress blue `#6EA8FF`; review `#D2A6FF`; done and on track green `#5ED39A`; planned, inbox, cancelled grey.
- **Tint backgrounds (chips, row washes) only for the two states that demand action: blocked and overdue.** Everything else is a dot plus a word on the neutral surface.
- **Priority is not a colour.** A 3-character mark: `P1` / `P2` / `P3` mapped from high / medium / low, in ink weight (700, 500, 400 muted) so red stays unambiguous.
- **No filled accent card.** `AccentCard` is retired (see Open question 1). Focus is the hero through position and size, not fill.
- **Charts** use the same hues and only where they decide something (5.4, 5.5). No gradients, no glow.

### 5.4 Dashboard redesign

Target at 1920: one screen (about 1000px) instead of 2183px. Order follows the request: understand, decide, prioritise, execute, record.

```
+ top bar 52: Tuesday 6 Oct | search (Ctrl+K) | context | [+ New] | avatar            +
| strip: 5 for today | 2 in progress | 2 blocked | 2 overdue | 4 inbox | 3 decisions |
+-------------------------+-------------------------+----------------------------+
| Focus (5 rows, inline   | Blocked and waiting     | Standup today (write in    |
| status, priority, why)  | Decisions to make       | place) + schedule (preview)|
| Active projects (table) | Done recently           | Learning (preview, 1 row)  |
+-------------------------+-------------------------+----------------------------+
```

| Current section | Verdict | Why and how |
|---|---|---|
| Header (2 rows) | **Merge** into a 52px bar | Title, search with Ctrl+K, context select, one "New" menu (the five dialogs), avatar. Index pill only shows when problems exist. Start standup moves into the Standup panel |
| Stat tiles | **Merge** into a one-line status strip | Same counts and links (`tasksHref`), plus "decisions pending". Replaces 5 boxes and the donut's information. Each figure links to the filtered list |
| Today's focus | **Keep, change** | Remains the hero and the rule is unchanged. Neutral surface, one-line row: priority mark, title, project, reason, status control. **Inline status change** (existing `changeStatus`, optimistic) and a "record progress" action that uses `evidence` on done. The first row gets a "Next" marker. Footnote becomes a tooltip |
| Needs attention | **Redesign** | Becomes "Blocked and waiting": blocked tasks with reason and age, one per row. Overdue and high priority are dropped as lists because Focus already shows them with markers; the strip still counts them. Critical incidents N/A row deleted until Phase 2 |
| (new) Decisions to make | **Add** | Notes of type `decision`, status `proposed`: title, project, age. Answers "help me decide" with Phase 1 data. Row opens the note reader |
| Tasks by status | **Drop from Dashboard** | Not a daily decision. Becomes a one-line segmented filter in the Tasks page header. Donut component kept for Project view progress if wanted |
| Active projects | **Keep, change** | One ruled row per project: name, health word, "next or blocked item", `1 of 4`, thin bar. Row opens the project view. Health rule behind an info tooltip |
| Today's meetings | **Merge** into the Standup panel as a "Schedule" section | Still labelled preview (Calendar, Phase 4) |
| Today's standup | **Promote and merge** | Shows Done, Today, Blockers inline with an add field per section (uses the append endpoint); "Start standup" when not started; link to history |
| Workflow stages | **Move** to the Workflow page | Entirely invented data (needs a stage per task, not in the plan). A strip of six stage tiles with a rework line is the clearest case of a chart added to look good |
| Recent activity | **Redesign** as "Done recently" | Tasks moved to done in the last 7 days with the evidence line, then lesser vault activity under "Activity". Answers "what did I accomplish". Note: only `modified` time is stored, so "completed on" is approximate (Open question 4) |
| How you are improving | **Shrink** | One preview row for Learning with its Phase 3 label. Claude usage dropped: it answers no question in the request |
| Integrations | **Drop from Dashboard** | Not a daily need; one line in Index status or a later Settings page |

Result: 10 cards plus 5 tiles plus 6 tiles become 6 panels and a strip. Nothing is invented; real panels are 5 of 6.

### 5.5 The other pages

Priority order for building (reasoning: daily value, then dependencies; the phase plan's own page order is Dashboard, Tasks, Inbox, then the rest, see Open question 5).

1. **Tasks with the note reader.** Answers: what is open, what is blocked, what is due, across all projects.
   Layout: filter bar (status segments, project, priority, due; URL driven via `tasksHref`), grouped table (group by project, status or due), 32px rows with priority, status control, due, project. Selecting a row opens the **note reader in a right pane (split view), not a modal**; at 1920 the list is 5/12 and the reader 7/12; below 1024 the reader is its own route. Reader: title, status control, due, project, rendered body, links and backlinks, evidence field on done. Header strip shows the status distribution as one segmented bar that filters.
2. **Standup.** Answers: what did I do, what is today, what blocks me, what repeats.
   Layout: left, today's six sections as editable blocks with add field and related task chips; right, history list of previous days with carry-over marks. "Patterns" tab (recurring blockers by count and days open) computed from standup notes; a small bar list only if it holds data.
3. **Projects and project view.** List: table with health, open, blocked, overdue, next item, last activity. View: header (status, health word, stage if known), tabs **Overview, Tasks, Decisions, Notes**, with Timeline, Incidents, Deployments and Learning tabs shown as labelled "Later". Overview is two columns: blockers and next tasks on the left, decisions and recent notes on the right, one progress bar. "Understand the project without searching" is met by the Overview alone.
4. **Inbox.** Answers: what do I sort now. Row per capture with five inline triage actions (task, decision, lesson, project, dismiss) using the existing triage endpoint; keyboard friendly; empty state says "Inbox clear".
5. **Knowledge and Decisions.** One list pattern, two routes. Rows: title, project, status (decisions: proposed, accepted, superseded, rejected), date. Reader pane as in Tasks. Decisions group by status with "proposed" first.
6. **Search.** Ctrl+K palette for quick jumps; `/search` page for result lists with type filters and snippets, grouped by type.
7. **Index status.** Counts by type, the problem list with links to the offending notes, last pass, refresh button. Integrations stub sits here.
8. **Workflow, Timeline, Upskilling (preview).** Each keeps a "Preview, sample data" banner with the phase. Workflow: stage columns (kanban, read only) plus the rework list. Timeline: vertical date-grouped feed with a type filter. Upskilling: current topics, practice and applied counts, skill gaps linked to the tasks that exposed them. Each answers one stated question or gets cut.

### 5.6 Responsive plan

| Width | Changes |
|---|---|
| 1280 and up | Full rail 224px; 2 or 3 columns; table density 32px; reader as split pane |
| 832 to 1279 | 56px icon rail with tooltips; 2 columns (8/4) that collapse to 1 under 900; reader opens as route or overlay pane |
| 640 to 831 | No rail; top bar with menu; bottom tab bar; panels 1 column, small panels 2-up |
| Under 640 | Top bar 48px (title, search icon, +). Strip becomes a horizontal chip scroller. Bottom tab bar: Today, Tasks, Standup, Projects, More; floating capture button. Tables become two-line cards-as-rows (title, then status, priority, due) |

Mobile shows first, in this order: status strip, Focus (with the status control), Blocked, Decisions, Standup (add a line), Projects (one line each), then Done recently. Learning and previews hide behind "More". Header controls (context select) collapse into the top bar menu. The filled capture button is reachable by thumb. No tab ever shows a table wider than the screen.

### 5.7 Components

| Component | Action | Note |
|---|---|---|
| `Card`, `CardHead`, `CardRow` | **Change** | Rename to Panel semantics, 12px radius, 12px padding, 40px header, 36 and 48px rows |
| `InsetItem` | **Change** | Remove from Dashboard; keep for forms only |
| `AccentCard` | **Retire** | Pending Open question 1 |
| `StatTile` | **Replace** by `StatStrip` | One bar, linked counts |
| `StatusChip` | **Keep, change** | Dot plus word; tint only for blocked and overdue |
| `Segmented` | **Keep** | Used for context, filters, status distribution |
| `Donut` | **Keep, unused on Today** | Project view only if it answers something |
| `ProgressBar`, `ActivityList`, `EmptyState`, `ErrorState`, `QueryBoundary`, `Toast` | **Keep** | |
| `Rail`, `Header`, `AppShell`, `nav.ts` | **Change** | Icon rail, top bar, Later group, mobile tab bar |
| `QuickActions` | **Change** | One New menu with shortcuts; dialogs unchanged |
| `TaskRow`, `PriorityMark` | **Add** | Shared by Today, Tasks, Project, Search |
| `StatusMenu` | **Add** | Inline status change with optimistic update, 409 handling, evidence on done |
| `NoteReader`, `SplitPane` | **Add** | Reader and the layout that hosts it |
| `FilterBar`, `DataTable` | **Add** | URL-driven filters; dense table |
| `MobileTabBar`, `CommandPalette` | **Add** | Phone navigation; Ctrl+K |
| `PreviewBadge` | **Add** | One labelled badge replacing repeated source captions |

## 6. Work packages

Each package owns its files; none edits another's. `src/routes.tsx` is edited only by the orchestrator when merging a page package, to avoid conflicts. "Safe" means no structural change and can start on go-ahead of this document being read; "Structural" needs your approval first.

| # | Package | Owns | Depends on | Class |
|---|---|---|---|---|
| WP0 | Tokens: type and spacing scale, radius, 12px caption contrast, `faint` check, weight cap | `src/index.css` | none | Safe |
| WP1 | Shared primitives: Panel (Card), StatusChip, StatStrip, PriorityMark, PreviewBadge, TaskRow, StatusMenu | `components/` (new files and Card, StatusChip, StatTile) | WP0 | Safe |
| WP2 | App shell: top bar, icon rail, Later group, mobile tab bar, New menu, Ctrl+K hook | `AppShell`, `Rail`, `Header`, `nav.ts`, `QuickActions` entry, `MobileTabBar` | WP0, WP1 | **Structural** |
| WP3 | Dashboard rebuild per 5.4, and its tests | `features/dashboard/*`, `sections.test.tsx` | WP1, WP2 | **Structural** |
| WP4 | Tasks page and NoteReader | `features/tasks/`, `features/notes/` | WP1, WP2 | Safe (already planned P1-34, P1-32) |
| WP5 | Standup page and history | `features/standup/` | WP1, WP2 | Safe |
| WP6 | Projects list and project view | `features/projects/` | WP1, WP2, WP4 reader | **Structural** (project view tabs) |
| WP7 | Inbox page | `features/inbox/` | WP1, WP4 reader | Safe |
| WP8 | Knowledge and Decisions pages | `features/knowledge/` | WP1, WP4 reader | Safe |
| WP9 | Search page and command palette | `features/search/`, `components/CommandPalette` | WP2 | Safe |
| WP10 | Index status page | `features/index-status/` | WP1 | Safe |
| WP11 | Preview pages (Workflow, Timeline, Upskilling) | `features/preview/` | WP1 | Safe |
| WP12 | Responsive check at 1920, 1440, 1024, 390 plus contrast pass and screenshots | tests and `docs/design/` only | after each page | Safe |

Parallelism: WP0 then WP1 are the only serial gate. After WP1, WP2, WP4, WP5, WP10 and WP11 can run in parallel; WP3, WP6, WP7, WP8, WP9 follow once WP2 (and the reader for 6, 7, 8) is merged. Each agent that implements is reviewed by a different agent, per the project rules; the orchestrator runs the tests.

## 7. Open questions for the user

1. **Retire the filled violet card?** `theme.md` allows one accent card per page (Today's focus); `app-request.md` says colour should communicate status and avoid decoration. This proposal retires it. Say if you want to keep the violet hero.
2. **Context switcher scope.** Should "All projects / LoadUp / IPP" filter every page and panel (as the route comment already intends), or only Today and Tasks?
3. **Follow-ups.** The Follow-up button exists but no source is defined for listing them. Are they lines under the standup's Follow-ups heading, or should they become task notes? This decides whether the Dashboard can show them in Phase 1.
4. **"Done recently" accuracy.** Only the note's modified time is indexed, so the completion date is approximate. Accept that for now, or add a completed date to the data model (not UI-only)?
5. **Build order.** The plan's page order is Tasks, then Inbox. This proposal wants Standup before Inbox. Keep the plan's order or reorder?
6. **Preview pages in the rail.** Hide Workflow, Timeline and Upskilling under a collapsed "Later" group, or leave them visible as now?

## 8. Addendum: metrics and charts stay (user instruction, 2026-10-06)

After reading this proposal the user said the app must still have metrics and
charts for visualisation. Section 5.4 is amended as follows; the rest of the
proposal stands.

| Section 5.4 item | Amended verdict |
|---|---|
| Stat tiles | **Keep as compact tiles**, not a text strip: 64px high, icon chip, figure and label on one line each, six across at 1920 (For today, In progress, Blocked, Overdue, Inbox, Decisions pending), each still a link to its list |
| Tasks by status | **Keep on the Dashboard** as a small donut (120px) with its legend of counts, placed beside Active projects; it also becomes the segmented filter in the Tasks header |
| Active projects | As proposed, with the progress bar kept |
| Workflow stages | **Keep** as a compact six-figure strip with the rework line, labelled preview, below the main columns rather than between them |
| Done recently | Add a small 7-day bar of tasks done per day beside the list (approximate, from modified time; Open question 4) |
| Other pages | Keep every chart the prototype screens have where it answers a question: status bar in Tasks, work-by-project and recurring-blocker bars in Standup, progress and status donut in the project view, events-per-day area chart in Timeline, learning-per-week bars in Upskilling |

Rules that still apply: every chart has a heading phrased as the question it
answers, shows its numbers as text, uses the status hues only, and preview
data is labelled. Density targets of 5.2 apply to charts too: no chart taller
than 160px on the Dashboard.

## 9. Decisions (user go-ahead, 2026-10-06)

The user approved the structural packages ("go") and the recommended answers
to section 7:

1. The filled violet Focus card is retired; accent means interaction, colour means status.
2. The project context switcher filters every page and panel, through the `project` query parameter.
3. Follow-ups are lines under the standup's Follow-ups heading (Phase 1 data), not task notes.
4. "Done recently" uses the note's modified time as an approximate completion date, labelled as such.
5. Build order: Tasks, Standup, Projects, Inbox, then Knowledge and Decisions, Search, Index status, previews.
6. Workflow, Timeline and Upskilling sit under a collapsed "Later" group in the rail.

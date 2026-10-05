# Theme v2: dark, card-based command center

The user reviewed the prototype and asked for a redesign of the look, based on
three sample dashboards, in a dark theme, keeping every feature. This file
replaces the "Look" section of `BRIEF.md`. Everything else in `BRIEF.md`
(format rules, navigation contract, sample data, honesty rules, what not to
do, report shape) still applies.

## Contents

- [The samples and what to take from them](#the-samples-and-what-to-take-from-them)
- [What changes and what does not](#what-changes-and-what-does-not)
- [Tokens](#tokens)
- [Shared helmet](#shared-helmet)
- [Component patterns](#component-patterns)
- [Icons](#icons)
- [Charts](#charts)
- [Colour mapping from the old theme](#colour-mapping-from-the-old-theme)
- [Checks before you report](#checks-before-you-report)

## The samples and what to take from them

Read the three images with the Read tool:

- `/tmp/claude-1000/-mnt-d-Projects-second-brain-workflow/b7758dd7-f159-4f76-bffd-9081ca9ec41b/images/7.jpg`
  (a "second brain" dashboard: greeting headline, stat tiles with icon chips,
  one filled accent tile, pill tabs, item cards with tinted tags, an activity
  list with a dotted rail, a connected-apps list with status pills).
- `.../images/10.png` (analytics: stat cards with small delta tags, an area
  chart, rounded bars, a donut with a centre value, pill-shaped active nav).
- `.../images/11.png` (dark task dashboard: charcoal cards on a darker
  ground, stat tiles with round icon chips, line chart with markers, donut,
  a simple table, project progress bars).

Take: the dark charcoal ground with slightly lighter rounded cards; generous
radius; stat tiles with an icon chip, a big value and a small label; one
filled accent card per page for the single most important thing; pill tabs and
tinted status tags; a rail with icon plus label and a filled pill for the
current item; donut, area and rounded-bar charts where they answer a question;
progress bars for projects; a dotted-rail activity list; comfortable spacing.

Do not take: the samples' brand names, logos, illustrations, avatars or copy;
glow or gradient backgrounds; fake deltas ("up 14% this month") or scores
("88% productivity") that our data cannot produce; pricing or upgrade panels.
Our own honesty rules still hold: `N/A`, `Estimated`, stated health rule,
source and phase notes.

## What changes and what does not

- Changes: colours, typeface, radius, spacing, the rail, the header, stat
  tiles, chart forms, tag style. Lists that were ruled ledgers become rows
  inside rounded cards. Where a section was text and counts only and a chart
  form from the samples answers the same question better, use it (see
  [Charts](#charts)).
- Does not change: your page's sections, features, interactions, sample data,
  links between artboards, phase and source notes, accessibility rules, and
  everything in `renderVals()` except colours and any values a new chart needs.
- Still true: sentence case, no all-caps labels, no emoji, status always has a
  word, real buttons and links, works at phone width.

## Tokens

| Token | Value | Use |
|---|---|---|
| Ground | `#0F0F14` | page background |
| Rail | `#15151C` | left rail, header |
| Card | `#1B1B24` | cards |
| Inset | `#242430` | tiles inside cards, inputs, table header, tracks |
| Line | `#2F2F3D` | borders, dividers |
| Text | `#F3F3F8` | primary text |
| Muted | `#A3A3B5` | secondary text (do not go darker than this for text) |
| Accent | `#9B8CFF` | links, current item, chart primary, focus ring |
| Accent fill | `#6B58E6` | filled buttons and the one filled accent card (white text on it) |
| Accent soft | `#2A2550` | tinted backgrounds behind accent text and icons |
| In progress | `#6EA8FF` | status |
| Blocked, overdue, failed | `#FF7D73` | status, warnings |
| At risk, warning | `#F5B85C` | status |
| Done, on track | `#5ED39A` | status |
| Review | `#D2A6FF` | status |
| Planned, inbox, neutral | `#A3A3B5` | status |
| Cancelled | `#7D7D90` | status (only with a word; never for body text) |

Typeface: Plus Jakarta Sans for everything; DM Mono only for literal vault
text (paths, frontmatter values, wikilink brackets, `##`). Radius: cards 16px,
tiles and inputs 12px, buttons 10px, tags and pill tabs fully round.

## Shared helmet

Replace the shared part of your `<helmet>` (everything copied from Main) with
this block exactly, then restyle the classes you added yourself so they fit
it. Keep your own class names.

```html
<helmet>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap">
<style>
body{margin:0;font-family:'Plus Jakarta Sans',system-ui,sans-serif;color:#F3F3F8;background:#0F0F14;font-size:14px;line-height:1.5}
*{box-sizing:border-box}
a{color:#9B8CFF}a:hover{color:#BDB2FF}
button,input,select,textarea{font:inherit;color:inherit}
:focus-visible{outline:2px solid #9B8CFF;outline-offset:2px}
h1,h2,h3{margin:0;font-weight:700;letter-spacing:-0.01em}
.day{font-size:clamp(24px,3.2vw,34px);font-weight:800;letter-spacing:-0.02em;line-height:1.15}
.mono{font-family:'DM Mono',ui-monospace,monospace;font-size:12px}
.num{font-variant-numeric:tabular-nums}
.muted{color:#A3A3B5}
.note{font-size:12px;color:#A3A3B5}
.btn{min-height:38px;padding:0 14px;border:1px solid #2F2F3D;background:#242430;color:#F3F3F8;border-radius:10px;cursor:pointer;display:inline-flex;align-items:center;gap:8px;font-weight:600;white-space:nowrap;text-decoration:none}
.btn:hover{background:#2F2F3D;color:#F3F3F8}
.btn:disabled{opacity:.45;cursor:not-allowed}
.btn.primary{background:#6B58E6;border-color:#6B58E6;color:#FFFFFF}
.btn.primary:hover{background:#7C6AF0;color:#FFFFFF}
.btn.small{min-height:32px;padding:0 12px;font-size:13px}
.linkbtn{background:none;border:0;padding:0;cursor:pointer;color:#F3F3F8;font-weight:600;text-align:left;text-decoration:none}
.linkbtn:hover{color:#BDB2FF;text-decoration:underline;text-underline-offset:3px}
.wl{color:#9B8CFF}
.wl::before{content:"[[";font-family:'DM Mono',monospace;font-size:12px;font-weight:400;color:#7D7D90}
.wl::after{content:"]]";font-family:'DM Mono',monospace;font-size:12px;font-weight:400;color:#7D7D90}
.chip{display:inline-flex;align-items:center;gap:6px;height:24px;padding:0 10px;border:0 !important;border-radius:999px;background:#242430 !important;font-size:12px;font-weight:600;white-space:nowrap}
.chip::before{content:"";flex:none;width:7px;height:7px;border-radius:50%;background:currentColor}
.card{background:#1B1B24;border:1px solid #2F2F3D;border-radius:16px}
.card-head{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;padding:16px 20px 12px}
.card-head h2{font-size:16px}
.card.accent{background:#6B58E6;border-color:#6B58E6;color:#FFFFFF}
.card.accent .muted,.card.accent .note{color:#E4DFFF}
.tile{display:flex;align-items:center;gap:14px;padding:16px 18px;background:#1B1B24;border:1px solid #2F2F3D;border-radius:16px;text-align:left;color:#F3F3F8;text-decoration:none}
button.tile,a.tile{cursor:pointer}
button.tile:hover,a.tile:hover{border-color:#6B58E6;color:#F3F3F8}
.tile-v{font-size:26px;font-weight:800;line-height:1.1;font-variant-numeric:tabular-nums}
.tile-l{font-size:13px;color:#A3A3B5}
.icon{flex:none;width:42px;height:42px;border-radius:12px;display:inline-flex;align-items:center;justify-content:center;background:#2A2550;color:#9B8CFF}
.icon.sm{width:30px;height:30px;border-radius:9px}
.icon svg{width:20px;height:20px}
.row{display:grid;align-items:center;gap:12px;padding:11px 20px;border-top:1px solid #2F2F3D}
.head{font-size:12px;font-weight:600;color:#A3A3B5;background:#242430;border-top:0}
.scroll{overflow-x:auto}
.empty{padding:20px;color:#A3A3B5}
.field{display:flex;flex-direction:column;gap:6px;font-size:12px;font-weight:600;color:#A3A3B5}
.input{min-height:38px;padding:6px 12px;border:1px solid #2F2F3D;border-radius:10px;background:#242430;font-weight:400;font-size:14px;color:#F3F3F8}
.input::placeholder{color:#7D7D90}
.nav{display:flex;flex-direction:column;gap:2px}
.nav-item{display:flex;align-items:center;gap:10px;min-height:40px;padding:0 12px;border:0;border-radius:10px;background:none;cursor:pointer;font-weight:600;color:#A3A3B5;text-align:left;text-decoration:none}
.nav-item svg{flex:none;width:18px;height:18px}
.nav-item:hover{background:#242430;color:#F3F3F8}
.nav-item.on{background:#6B58E6;color:#FFFFFF}
.nav-item .count{margin-left:auto}
.count{font-size:12px;font-weight:700;padding:1px 8px;border-radius:999px;background:#242430;color:#F3F3F8;font-variant-numeric:tabular-nums}
.seg{min-height:32px;padding:0 14px;border:0;background:none;color:#A3A3B5;border-radius:999px;cursor:pointer;font-size:13px;font-weight:600;text-decoration:none;display:inline-flex;align-items:center}
.seg:hover{background:#2F2F3D;color:#F3F3F8}
.seg.on{background:#6B58E6;color:#FFFFFF}
.segs{display:inline-flex;flex-wrap:wrap;gap:2px;padding:4px;background:#242430;border-radius:999px}
.track{height:8px;border-radius:999px;background:#242430;overflow:hidden}
.fill{height:8px;border-radius:999px;background:#9B8CFF}
.rail-list{position:relative;padding-left:22px}
.rail-list::before{content:"";position:absolute;left:5px;top:6px;bottom:6px;width:1px;background:#2F2F3D}
.rail-dot{position:absolute;left:-21px;top:7px;width:9px;height:9px;border-radius:50%;background:#9B8CFF;box-shadow:0 0 0 3px #1B1B24}
.line{display:flex;align-items:baseline;gap:8px;padding:3px 0}
.box{flex:none;width:14px;height:14px;border:1.5px solid #A3A3B5;border-radius:4px;position:relative;top:2px}
.box.done{background:#9B8CFF;border-color:#9B8CFF}
.sec-h{font-size:12px;font-weight:600;color:#7D7D90;margin:0 0 4px}
.md-h{font-size:15px;font-weight:700;margin:0 0 4px}
.hash{font-family:'DM Mono',monospace;font-weight:400;font-size:13px;color:#7D7D90}
@media (max-width:820px){.nav{flex-direction:row;flex-wrap:wrap}.nav-item{min-height:44px}.btn,.seg,.input{min-height:44px}}
</style>
</helmet>
```

Notes on the block:

- `.sec-h` uses `#7D7D90` only for the small rail group labels. If you use
  `.sec-h` for anything a person must read, give it `color:#A3A3B5` inline.
- `.chip` now ignores the `background` and `border-color` you pass inline and
  uses the inline `color` for its dot and text. Pass a status colour from the
  token table as the chip's `color`.
- `.tally`, `.tally-n`, `.tally-t` are gone: use `.tile` stat tiles instead.
- Wrap a group of `.seg` buttons in `<div class="segs">` to get the pill tab
  bar from the samples.

## Component patterns

- **Rail:** background `#15151C`, right border `#2F2F3D`, padding 20px 14px.
  Product name "Second Brain" in 17px 800 with a small accent square mark
  before it (a plain `<span>` 22px square, radius 7px, background `#6B58E6`),
  the vault path under it in mono. Each item: icon then label. Keep the four
  group labels.
- **Header:** background `#0F0F14` (no bar colour), padding 20px 28px 8px, the
  page title large (24px 800), under it one muted line saying what the page
  is for. Search as a rounded input with a search icon. Context switcher as a
  `.segs` pill pair. User as a round 36px initial "R" on `#2A2550`.
- **Stat tile:** `.tile` with `.icon` (pick the icon's tint from the status
  tokens: put `background` and `color` inline, for example
  `background:#3A2422;color:#FF7D73` for blocked, `background:#1E3329;color:#5ED39A`
  for done, `background:#3A3020;color:#F5B85C` for at risk,
  `background:#1F2C44;color:#6EA8FF` for in progress), then a column with
  `.tile-v` and `.tile-l`. A row of tiles is a grid
  `repeat(auto-fit, minmax(min(210px, 100%), 1fr))` with gap 16px.
- **One accent card per page:** `.card.accent` for the single most important
  thing on that page (for example Today's focus on the dashboard, the current
  roadmap week on Upskilling). Never more than one.
- **Cards:** gap 20px between cards; card padding 20px (or `.card-head` plus
  `.row`s). A page is a grid of cards, not one long column: use two or three
  columns at 1440 where the content allows, collapsing by auto-fit.
- **Item card inside a card** (as in sample 1's recent captures): background
  `#242430`, radius 12px, padding 14px, icon chip, title, one muted meta
  line, one tag.
- **Tag:** `.chip`.
- **Progress:** `.track` with `.fill` inside; width from a style hole in value
  position; the counts as text beside it ("1 of 4 done"), never a bare
  percentage the data cannot support.
- **Activity list:** `.rail-list` with each entry `position:relative` and a
  `.rail-dot` as its first child.
- **Diagrams** (workflow, architecture): nodes are rounded 12px boxes on
  `#242430` with a 1px `#2F2F3D` border; the current node has a 2px `#9B8CFF`
  border; a failed node a 2px `#FF7D73` border; arrows `#7D7D90`, the rework
  loop `#FF7D73`. Recompute nothing: keep your positions, change colours.

## Icons

Inline stroke SVG only, 24 by 24 viewBox, `fill="none" stroke="currentColor"
stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"`, with
`aria-hidden="true"` when beside a label. Use these paths for the rail so all
six artboards match:

| Item | Inner markup |
|---|---|
| Dashboard | `<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>` |
| Standup | `<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.7A8 8 0 1 1 21 12z"/>` |
| Inbox | `<path d="M3 13l3-8h12l3 8v6H3z"/><path d="M3 13h5l1.5 3h5L16 13h5"/>` |
| Tasks | `<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8.5 12l2.5 2.5 4.5-5"/>` |
| Projects | `<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>` |
| Workflow | `<circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="12" r="2.5"/><path d="M6 8.5v7"/><path d="M8.5 6H13a5 5 0 0 1 5 3.5"/>` |
| Timeline | `<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>` |
| Knowledge | `<path d="M5 4h10a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"/><path d="M5 17a3 3 0 0 1 3-3h10"/>` |
| Decisions | `<path d="M12 3v18"/><path d="M12 6h7l-2 3 2 3h-7"/><path d="M12 13H5l2 2.5L5 18h7"/>` |
| Upskilling | `<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>` |
| Search | `<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>` |
| Index status | `<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>` |

For other icons (alert, calendar, check, plus, clock, flag, book) draw simple
ones in the same style. No emoji, no icon fonts.

## Charts

Use the `dataviz` skill's method; colours from the token table. Forms from
the samples, used only where they answer a question on your page:

- **Donut** (parts of a whole, for example tasks by status): a `<div>` with
  `border-radius:50%` and `background: {{donutBg}}` where `renderVals()`
  builds a `conic-gradient(...)` string from the counts, with a smaller
  centred `<div>` in the card colour holding the total and its label. Put the
  legend beside it as rows: colour dot, word, count. Do not build a donut from
  `<sc-for>` inside `<svg>`.
- **Area or line** (a count over days): one inline `<svg>` with
  `viewBox` and `preserveAspectRatio="none"`, a `<path d="{{areaPath}}">` for
  the fill (accent at about 25% opacity via `fill-opacity`) and a
  `<path d="{{linePath}}">` for the line, both strings built in
  `renderVals()`. Day labels and values go in HTML under and over the plot,
  not inside the svg. Never put `<sc-for>` or `<sc-if>` inside `<svg>`.
- **Rounded bars**: flex or grid of `<div>`s with a height or width style
  hole and radius 8px, values as text.
- Every chart keeps a heading phrased as the question it answers, the numbers
  as text, and a note of where the data comes from when it is a later phase.
  No chart for decoration: if the counts alone answer it, keep the counts.

## Colour mapping from the old theme

Replace old hex values everywhere in your file (markup and script):

| Old | New |
|---|---|
| `#EEF2E6` ground, `#E7EDDD`, `#E3EADA` | `#0F0F14` for page, `#242430` for insets |
| `#FBFCF7` surface | `#1B1B24` |
| `#1B2A22` ink (text) | `#F3F3F8` |
| `#1B2A22` used as a fill or 2px rule | `#2F2F3D` for rules, `#6B58E6` for filled selected states |
| `#3A4A40`, `#55635A`, `#66726A` muted text | `#A3A3B5` |
| `#C9D3BE`, `#DCE4D2`, `#AEBAA3` rules and borders | `#2F2F3D` |
| `#1D4E89` action blue | `#9B8CFF` for links and accents, `#6EA8FF` for the in-progress status, `#6B58E6` for filled buttons |
| `#A3341F` red | `#FF7D73` |
| `#F6E3DC` red tint | `#3A2422` |
| `#2F6B3F` green | `#5ED39A` |
| `#E1EEDD` green tint | `#1E3329` |
| `#5B3A8C` violet | `#D2A6FF` |
| `#8A5A00` amber (if present) | `#F5B85C` |
| `#8C9A8F` | `#7D7D90` |
| any white text on a dark fill (`#FFFFFF`, `#FBFCF7` as text) | `#FFFFFF` only on `#6B58E6`; otherwise `#F3F3F8` |
| toast background | `#F3F3F8` with text `#0F0F14` |
| overlay behind a modal or drawer | `rgba(0, 0, 0, 0.6)` |

After mapping, search your file for any remaining light hex (anything starting
`#E`, `#F` other than the tokens above, `#D`, `#C`) and fix it by meaning.

## Checks before you report

- No old-theme hex left; no light backgrounds; text on every surface meets
  4.5 to 1 (muted `#A3A3B5` on `#1B1B24` and `#242430` passes; `#7D7D90` is
  only for group labels and brackets).
- White text only on `#6B58E6`.
- `node --check` on the extracted script passes; every `{{name}}` in markup is
  returned by `renderVals()`; tags balanced; no `sc-for` or `sc-if` inside
  `svg`, `table` or `select`.
- All features and links you had before still exist. List anything you
  removed.
- Do not render, publish or touch other files.

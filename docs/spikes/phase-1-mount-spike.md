# Phase 1 mount spike: results

Task P1-02. Procedure and thresholds: `docs/plan/phase-1-foundation.md`
section 8. Raw numbers: `docs/spikes/phase-1-mount-spike-results.json`
(one key per measurement; the keys are named in the table below).

## Contents

- [1. Verdict](#1-verdict)
- [2. Setup as run](#2-setup-as-run)
- [3. Results table](#3-results-table)
- [4. Timing, projections and chosen parameters](#4-timing-projections-and-chosen-parameters)
- [5. Findings worth knowing](#5-findings-worth-knowing)
- [6. Decisions where section 8 was silent](#6-decisions-where-section-8-was-silent)
- [7. Operator checklist](#7-operator-checklist)
- [8. Reproducing and cleanup](#8-reproducing-and-cleanup)

## 1. Verdict

**Automated part: no fail.** Every measurement that needs no human passed or
is informational, with no soft passes. M1, the gating timing, projects to
0.93 s per pass at 1,000 notes against a 3 s pass threshold.

**Gate B cannot be called open yet.** Four result rows depend on Obsidian on
Windows and are `pending: operator`: M3 (the five Obsidian edits), M5b, M6 and
M7 (the Obsidian edit). Any of them can still produce a fail. Gate B is open
only when those rows are filled in (section 7) and none fails.

## 2. Setup as run

| Item | Value |
|---|---|
| Date | 2026-10-05 |
| Scratch corpus | `/mnt/d/sbw-spike/Spike Vault`: 5,000 `.md` files, 13,192,336 bytes, 20 folders, seed 20261005 |
| Docker / Compose | 28.3.2 / v2.39.1-desktop.1 |
| Image | `python:3.12-slim` (Python 3.12.14 in the container; 3.12.3 on the WSL host) |
| Mount as seen in the container | `D:\134 /vault 9p rw,noatime,aname=drvfs;path=D:\;uid=1000;gid=1000,cache=0x5,access=client,msize=65536` (WSL's drvfs, over 9p) |
| Container user | `1000:1000` |
| Selftest | `python3 web-app/scripts/spike/measure.py selftest`: 17/17 passed |

## 3. Results table

Verdict key: pass, soft pass, fail, informational, pending.

| # | Measurement | Measured | Threshold compared with | Verdict |
|---|---|---|---|---|
| M0 | Docker works in WSL | `docker compose version` and `docker run --rm hello-world` both succeed (key `M0`) | both succeed | **pass** |
| M1 | Stat-only walk (container, 5,000 files) | warm median 4,651.6 ms = 0.930 ms/file; 1 cold run 9,712 ms; warm runs 4,867 / 4,549 / 4,643 / 4,703 / 4,652 ms. 1,000-note projection **0.93 s**; 5,000-note projection 4.65 s (key `M1`). WSL-side run for comparison: 0.925 ms/file (`M1_host_wsl`) | pass at most 3 s at 1,000 notes; soft pass at most 10 s | **pass** |
| M2 | Full read + SHA-256 (container) | median 8,176 ms = 1.635 ms/file; runs 8,139 / 8,176 / 8,269 ms. 1,000-note projection **1.64 s**; 5,000-note projection 8.18 s (key `M2`) | pass at most 30 s at 1,000 notes | **informational** (would be a pass) |
| M3 | Host edits visible, edits from WSL | **20 edits**, `printf >>` over five files, gap 4.0 s plus uniform 0 to 0.5 s jitter, watcher in the container polling every 0.5 s: 20 of 20 seen. Edit-to-detect latency: min 0.016 s, median 0.235 s, p95 0.481 s, **max 0.503 s** (keys `M3_wsl_jitter`, `M3_wsl_edits_jitter`, `M3_wsl_watch_jitter`). The earlier two 5-edit runs (`M3_wsl`, `M3_wsl_run2`, fixed 4 s gap) were **aliased** with the 0.5 s poll and are kept only as history (see section 5) | all within 2 s | WSL half **pass**; Obsidian half **pending: operator** |
| M3 | Host edits visible, 5 edits in Obsidian | not run | 5 of 5 within 2 s (container detect time minus WSL-host detect time) | **pending: operator** |
| M4 | mtime resolution | stamped resolution no coarser than about 7 ms, stored in 100 ns units: the gcd of 40 `mtime_ns` values is 100 ns (the storage unit, not proof of 100 ns precision); 40 back-to-back rewrites gave 40 distinct mtimes; writes 50 ms apart differ by 58,052,200 ns (key `M4`) | recorded | **informational** |
| M5a | Atomic replace, file not open | 100 of 100 correct, 0 failures, 0 leftover temp files; mean 6.6 ms, max 11.7 ms per replace (key `M5a`) | 100 of 100, content correct | **pass** |
| M5b | Replace over a file open in Obsidian | not run | replace succeeds, Obsidian shows new content within 5 s, no revert, no dialog | **pending: operator** |
| M5c | Replace over a file locked by Windows | `powershell.exe` held the file open with `FileShare.Read`; a control append from WSL failed with Permission denied, so the lock was effective. The replace from the container raised `PermissionError: [Errno 13] Permission denied`; file content unchanged; no temp file left (key `M5c`) | the error surfaces as a Python exception | **pass** |
| M6 | Temp file invisible in Obsidian | not run | never shown | **pending: operator** |
| M7 | Ownership and permissions, automated part | file created in the container as uid 1000: mode 0777, owner uid/gid 1000; WSL `stat` reports `dubu:dubu 777`; `printf >>` from WSL succeeded; in a scratch repo committed with `core.filemode=true` (index mode 100755), after the edit `git status --porcelain` shows only ` M created-in-container.md` with `core.filemode=false` and with `core.filemode=true` (key `M7_auto`) | WSL user can edit without `sudo`; no mode-only diff | automated part **pass** |
| M7 | Ownership and permissions, Obsidian edit | not run | Obsidian can edit without `sudo` | **pending: operator** |
| M8 | Space in the path | `docker compose config` resolved `SPIKE_PATH` to `/mnt/d/sbw-spike/Spike Vault` and a `probe` run saw the marker file and 5,000 notes for **all three** forms: unquoted, double-quoted, single-quoted (key `M8`) | at least one form mounts the right folder | **pass** |
| M9 | Read-only mount | in `probe_ro`: create file, open an existing note for append and `mkdir` each failed with errno 30 (`EROFS`) (key `M9`) | fails with `EROFS` | **pass** |
| M10 | Case collisions | `Case.md` created; creating `case.md` raised `FileExistsError`; the folder listing shows one file: the mount is case-insensitive (key `M10`) | recorded | **informational**: confirms section 2.5 |
| M11 | Illegal characters | `a:b.md` and `a?b.md` were both **created** without error from the container (key `M11`). Windows view recorded in the same key by `run.sh m11` (PowerShell `Get-ChildItem` code points): `0061 F03A 0062 002E 006D 0064` and `0061 F03F 0062 002E 006D 0064`, i.e. `a` U+F03A `b.md` and `a` U+F03F `b.md` (private-use substitutes), so Windows and Obsidian see different names | recorded | **informational**: confirms section 2.5 and adds a hazard (section 5) |
| M12 | Steady-state cost, 10 min, 5,000 files, poll every 10 s | 60 passes; pass time mean 4,662 ms (min 4,340, max 5,215), 0 passes over the interval; 0 changes seen. `docker stats` (52 samples): mean CPU **6.7%** of one core, peak 21.3% (one sample), memory about 17.6 MB; block I/O stayed `0B / 0B`. The poller's own CPU time was 6.3% of a core. These figures are the **container's CPU only**: the Windows-side 9p server that answers the stats sits outside the container's cgroup and is not counted (keys `M12_poll`, `M12_stats`) | recorded; mean above 10% of a core is a risk | **informational**: mean 6.7% of container CPU is below the 10% risk line; total cost including Windows is not measured |

## 4. Timing, projections and chosen parameters

| Quantity | ms per file | 1,000 notes | 5,000 notes |
|---|---|---|---|
| Stat-only walk, warm median (M1) | 0.930 | 0.93 s | 4.65 s |
| Stat-only walk, first run in a fresh process (M1 cold) | 1.942 | 1.94 s | 9.71 s |
| Read + SHA-256 (M2) | 1.635 | 1.64 s | 8.18 s |
| Poll pass during M12 (mean of 60) | 0.932 | 0.93 s | 4.66 s |

Against section 2.7: the steady-state pass budget (at most 3 s at 1,000 notes,
under the poll interval) is met with margin, and the full-`reindex` budget (at
most 30 s at 1,000 notes) is met by the read and hash cost alone. Risks,
recorded as the plan asks, not gates:

- At 5,000 notes a steady-state pass takes about 4.7 s, 47% of a 10 s interval.
- **The first pass after an indexer start is the cold one**: 9.7 s for 5,000
  files, about 97% of a 10 s interval. Any indexer restart pays it. The cold
  figure is the first run in a new process, not a dropped page cache; the cache
  on a 9p mount is managed by the WSL kernel and the spike does not control it.

| Parameter | Value | Basis |
|---|---|---|
| Recommended poll interval | **10 s** (keep `INDEXER_POLL_SECONDS=10`) | M1 passes outright, so no raise to 30 s. M12 ran at 10 s with no pass over the interval and mean container CPU 6.7%. Revisit if the vault passes roughly 2,000 notes (a pass would then use about 2 s of every 10 s). |
| mtime resolution | no coarser than about 7 ms, stored in 100 ns units | M4 |
| Racy window | **None recommended.** The indexer rule is clock-independent (plan section 2.7: every file a pass read is read again on the next pass) | The Windows-stamped mtime and the WSL clock disagree and drift against each other (section 5, finding 3), so a clock-based window cannot be justified from this evidence. |
| Container uid | 1000:1000 | The mount presents every file as uid/gid 1000, mode 0777, whoever created it. **Tested with uid 1000 only**; the claim that other uids behave the same is untested. |
| `.env` quoting form | all of `SPIKE_PATH=/mnt/d/sbw-spike/Spike Vault`, `SPIKE_PATH="/mnt/d/sbw-spike/Spike Vault"` and `SPIKE_PATH='/mnt/d/sbw-spike/Spike Vault'` worked (M8). `.env.example` uses the **double-quoted** form because it also survives `source .env` in a shell and other dotenv readers; the unquoted form works only because Compose reads to end of line. |

## 5. Findings worth knowing

1. **Illegal characters are not rejected, they are remapped.** Writing
   `a:b.md` through the mount succeeds, and Windows sees a different name
   (private-use U+F03A for `:`, U+F03F for `?`; recorded in key `M11`). A note
   created with such a name by the writer would exist under a name Obsidian and
   the user cannot type. The section 2.5 sanitising must therefore be done by
   the writer, not left to the filesystem to refuse.
2. **The mount is case-insensitive.** `case.md` cannot coexist with `Case.md`;
   the second create fails with `FileExistsError`. Matches section 2.5.
3. **Windows-stamped mtimes and the WSL clock disagree and drift.** Measured
   with `run.sh skew` (key `skew`): a file appended from WSL every 1.5 s for 660
   s (400 samples), recording `mtime` minus the WSL clock at the write.
   - Range: **-1.74 s to +1.32 s**, mean -0.29 s (positive means Windows is
     ahead).
   - Drift: **+0.105 s per second** within each segment (segment slopes 0.093
     to 0.109).
   - Resync: a step of about **-3.05 s** (jump relative to the drift, -3.03 to
     -3.22 s) 20 times, at 33.0 s intervals (first at 24 s, then every 33.0 to
     33.2 s), each time returning the skew to about -1.73 s.
   - So in this session the skew was a regular sawtooth with a period of about
     33 s and a peak-to-peak of about 3.1 s. The two 16-second M3 windows had
     seen only parts of it. This is one 11-minute session on one boot; its
     period and amplitude are not known to hold at other times (WSL idle,
     suspend, host load), so **the skew is treated as unbounded and drifting**,
     and the indexer's racy-file rule was made clock-independent for that
     reason (plan section 2.7). Any rule comparing an mtime with "now" is
     affected; the M3 latency figures are not, because they use the WSL clock
     at both ends.
4. **M3 WSL samples before the jitter were aliased.** The first two runs used a
   fixed 4 s gap, so every edit landed at nearly the same phase of the 0.5 s
   poll (each about 0.025 s later in the cycle). Eight of those ten samples
   sat in one 0.37 to 0.49 s band, one was 0.01 s, and one was 1.72 s. The
   jittered run (gap 4.0 s plus uniform 0 to 0.5 s, 20 edits) gave min 0.016,
   median 0.235, p95 0.481 and max 0.503 s: the spread expected from a 0.5 s
   poll, and the 1.72 s outlier did not recur. Its cause is unexplained and it
   remains the single sample outside the poll window.
5. **`docker stats` block I/O stayed at zero** during M12 because 9p reads do
   not appear in the container's block device counters, and its CPU excludes
   the Windows-side 9p server. The poller process time (6.3% of a core) and the
   container CPU (6.7%) are floors, not total cost.
6. **Scan time is the same inside and outside Docker** (0.930 vs 0.925 ms/file),
   so the cost is the drvfs/9p stat path in WSL, not the container layer.
7. **Obsidian steps use dot-directories.** Opening the scratch folder as a vault
   makes Obsidian create `.obsidian/`; the scripts' walk skips dot-directories,
   as the indexer will.

## 6. Decisions where section 8 was silent

- **Root guard.** Every script refuses a root that is not under
  `/mnt/d/sbw-spike/`, with one exception for the container, where the mount is
  `/vault`: there the root must contain `.sbw-spike-scratch`, a marker file
  `gen_corpus.py` writes at the corpus root and that a real vault never has.
  `gen_corpus.py` itself has no marker exception. `replace --target` and
  `replace --dir` must resolve inside the root. `assemble --out` may only write
  a `.json` file directly in `docs/spikes/`. `run.sh up` (and so every stage that
  starts containers) first checks that `SPIKE_PATH` from the env file resolves
  to the scratch corpus.
- **Compose project and lifecycle.** Project name `sbwspike`; `probe` and
  `probe_ro` are started with `sleep infinity` and used with `exec`;
  `network_mode: none`; scripts mounted read-only at `/spike`; torn down by
  `docker compose down`. The `.env` is read with `--env-file`.
- **M1 cold and warm.** "Cold" is the first run in a fresh process, not a
  dropped cache. The gate uses the warm median, as section 8 says. The stat
  walk skips dot-directories and dotfiles and counts `*.md` only, like the
  indexer in section 2.7.
- **M2.** One run is the first, two follow; the median of three is used.
- **M3 WSL half.** The watcher polls the five named files (not the whole
  corpus) every 0.5 s. Edits use `printf >>` through `bash`, one every 4.0 s
  plus uniform 0 to 0.5 s of jitter, cycling over the five files, 20 in all.
  Latency is detect time minus the edit time recorded just before the
  `printf`, both on the WSL VM clock (the container exec offset measured
  +0.11 to +0.15 s including half a round trip, so latencies carry about that
  much error). The verdict rule is unchanged: all within 2 s.
- **M3 Obsidian half.** There is no edit time for an Obsidian save, and mtime
  cannot stand in for one (finding 3: with Windows ahead, a real delay of 3.4 s
  could read as under 2 s). The step instead runs a second watcher on the WSL
  host at a 0.05 s poll on the same five files and reports, per file, the
  container's detect time minus the host's. Both watchers stop on five
  **distinct** files, not five events.
- **M5a.** The target is a scratch file in `_replace/`, replaced 100 times with
  1 to 2 KB payloads; each replace reads the file back and compares bytes.
- **M5c.** The lock uses `FileAccess.ReadWrite` with `FileShare.Read`, held 30
  s by `powershell.exe`. A control append from WSL proves the lock works. Run
  twice (the first attempt hit a drvfs `wslpath` lag and was discarded; the
  script now retries and aborts without attempting the replace if the lock was
  not taken).
- **M5b payload.** `replace --target` appends a plain line `REPLACED HH:MM:SS`
  to the file's existing content (an HTML comment could be hidden by Obsidian's
  Reading view or Live Preview).
- **M6.** The temp file lives for milliseconds, so the step runs
  `replace --dir _m5b --seconds 60 --pause-ms 50`: a replace loop in the folder
  the operator has expanded, on its own file `m6-loop.md`, for a minute, while
  the operator uses the explorer, search and quick switcher. The dotfile
  stand-in is a separate sub-check of Obsidian's hide-dotfiles rule only.
- **M7.** The scratch repository is `Spike Vault/_m7`, created by the script
  and removed after the automated run; `prep-operator` recreates it. The repo is committed with `core.filemode=true`, so the index records 100755 (the mount's 0777); committing under `filemode=false` records 100644, and `filemode=true` then reports a mode change on every file, which would be a false alarm. `git status` is run with both settings, so a mode change made by Obsidian would show with `true` and not with `false`.
- **M8.** Three forms were tried (the plan names two; single quotes added). A
  probe only runs when `compose config` resolves to the scratch folder, so a
  wrong form cannot make Docker create a stray host directory.
- **M11.** Re-run with `run.sh m11`, which keeps the files, lists them from
  Windows with PowerShell and stores the code points in the result.
- **M12.** Run at 10 s, the interval recommended after M1. CPU is sampled by
  `docker stats --no-stream` every 10 s (each call takes about a second, so 52
  samples in 10 minutes).
- **Stage artefacts.** Intermediate per-measurement JSON lives in
  `/mnt/d/sbw-spike/results/`; `run.sh assemble` writes the combined raw file.

## 7. Operator checklist

Obsidian on Windows is needed for every step below. Work through them in
order. Commands run in WSL from `/mnt/d/Projects/second-brain-workflow/web-app/scripts/spike`
unless a step says otherwise. Where a step says "record", write the value in
the matching row of section 3 and change `pending: operator` to a verdict.

**Step 0. Prepare (once)**

```
cd /mnt/d/Projects/second-brain-workflow/web-app/scripts/spike
./run.sh prep-operator
```

Observe: it prints `operator files ready under /mnt/d/sbw-spike/Spike Vault (_m3, _m5b, _m7)`.
It starts the two probe containers and creates `_m3/obsidian-1.md` to
`obsidian-5.md`, `_m5b/target.md`, and `_m7/created-in-container.md` (created
by the container as uid 1000, with a scratch git repository).

In Obsidian: "Open folder as vault", choose `D:\sbw-spike\Spike Vault`, trust
the folder if asked, install no plugins.

**Step 1. M3, five edits in Obsidian**

Two watchers, one in a container (0.5 s poll) and one on the WSL host (0.05 s
poll), each on the same five files. Open two WSL terminals in the directory
above.

Terminal A (container watcher):

```
./run.sh x watch --files _m3/obsidian-1.md _m3/obsidian-2.md _m3/obsidian-3.md _m3/obsidian-4.md _m3/obsidian-5.md --expect 5 --distinct --timeout 300 --interval 0.5 | ./run.sh save M3_obsidian_container
```

Terminal B (WSL host watcher):

```
python3 measure.py watch --root "/mnt/d/sbw-spike/Spike Vault" --files _m3/obsidian-1.md _m3/obsidian-2.md _m3/obsidian-3.md _m3/obsidian-4.md _m3/obsidian-5.md --expect 5 --distinct --timeout 300 --interval 0.05 | ./run.sh save M3_obsidian_host
```

**Wait until each terminal has printed `ready`**, then edit. Do: in Obsidian open
`obsidian-1.md`, type one character at the end, wait 5 seconds (Obsidian
autosaves after a short pause), then do the same for `obsidian-2.md` to
`obsidian-5.md`, one edit per file. Both commands exit by themselves once five
distinct files have been seen.

After:

```
python3 measure.py compare --container-json @/mnt/d/sbw-spike/results/M3_obsidian_container.json --host-json @/mnt/d/sbw-spike/results/M3_obsidian_host.json | tee /mnt/d/sbw-spike/results/M3_obsidian.json
```

Observe: `"all_within_2s": true`, `"max_delay_s"` at most 2.0, five entries in
`per_file`, all with `"seen": true`. The delay carries about 0.05 s plus up to
one container poll (0.5 s) of error. Pass: 5 of 5 within 2 s (the WSL half
already passed 20 of 20, so together they give the M3 verdict). Soft pass: all
within 10 s. Fail: a file the host watcher saw but the container watcher did
not see within 10 s (`"seen": false`), or a delay over 10 s. If neither watcher
saw a file, the edit was not saved: redo that file.

**Step 2. M5b, replace over a file open in Obsidian**

Before: in Obsidian click `_m5b/target.md` to open it in the editor, in Live
Preview or Source mode. Do not type in it, and keep it the active tab.

```
cat "/mnt/d/sbw-spike/Spike Vault/_m5b/target.md"
./run.sh x replace --target _m5b/target.md | ./run.sh save M5b
```

Observe, in this order: the command exits without error and
`/mnt/d/sbw-spike/results/M5b.json` shows `"ok": 1`, `"content_correct": true`.
In Obsidian, within 5 seconds and without clicking, the open note gains a last
line `REPLACED HH:MM:SS`. No conflict dialog or "file modified externally"
prompt appears.

After (wait 15 seconds without touching Obsidian):

```
cat "/mnt/d/sbw-spike/Spike Vault/_m5b/target.md"
```

Observe: the `REPLACED` line is still there (Obsidian did not write the old
content back). Pass: all of the above. Soft pass: Obsidian shows the new content
only after you click into the note. Fail: the replace fails, or the old content
comes back.

Not tested by this step: the dirty-editor case, a note with unsaved typing in it
when the replace lands. A pass here says nothing about that case.

**Step 3. M6, temp file invisible in Obsidian**

*3a. Replace loop (the real check).* Before: in Obsidian expand the `_m5b`
folder in the file explorer and leave it visible. Then start a 60 second loop in
that same folder (it uses its own file `m6-loop.md`, which appears and then
disappears; that is expected):

```
./run.sh x replace --dir _m5b --seconds 60 --pause-ms 50 | ./run.sh save M6_loop
```

Do, during the 60 seconds: keep watching the explorer; open search
(Ctrl+Shift+F) and search `sbw-tmp`, repeating it a few times; open the quick
switcher (Ctrl+O) and type `sbw-tmp`, repeating it a few times.

Observe: no entry named `.x.sbw-tmp-...` ever appears in the explorer, search
results or quick switcher. After the loop, `M6_loop.json` shows `"failures": 0`
and `"leftover_tmp": 0`.

*3b. Dotfile rule (separate sub-check: only tests that Obsidian hides
dotfiles, not the loop).*

```
printf x > "/mnt/d/sbw-spike/Spike Vault/_m5b/.x.sbw-tmp-demo"
```

Observe: the file is not in the explorer, search or quick switcher. Then
`rm "/mnt/d/sbw-spike/Spike Vault/_m5b/.x.sbw-tmp-demo"`.

Pass: 3a and 3b both never show the temp name. Fail: shown anywhere.

**Step 4. M7, Obsidian edit of a container-created file**

Before:

```
cd "/mnt/d/sbw-spike/Spike Vault/_m7"
stat -c '%U:%G %a %n' created-in-container.md
git status --porcelain
git -c core.filemode=true status --porcelain
```

Observe: owner `dubu:dubu`, mode `777`, and both `git status` commands print
nothing (clean). (The repo was committed with `core.filemode=true`, so mode 777 is the
recorded mode.)

Do: in Obsidian open `_m7/created-in-container.md`, type a line, wait 5 seconds.
Obsidian must save without any permission error.

After:

```
stat -c '%U:%G %a %n' created-in-container.md
git status --porcelain
git -c core.filemode=true status --porcelain
git -c core.filemode=true diff --summary
git diff --stat
printf 'edit from WSL after Obsidian\n' >> created-in-container.md && echo append-ok
```

Observe: owner and mode unchanged; both `git status` commands show only
` M created-in-container.md`; `git diff --summary` prints nothing (a line
`mode change 100644 => 100755` would be a mode-only change); `git diff --stat`
shows content lines added; `append-ok` is printed. Pass: Obsidian and WSL can
both edit without `sudo` and there is no mode change. Soft pass: a different
container uid is needed (record which). Fail: not editable from Obsidian or
WSL.

**Step 5. Finish**

1. Fill in the four pending rows of section 3 and the verdict in section 1.
2. `web-app/scripts/spike/run.sh assemble` regenerates the raw JSON including the Step 1, 2 and 3 files.
3. `web-app/scripts/spike/run.sh down` to remove the probe containers.
4. Close the vault in Obsidian, then delete `/mnt/d/sbw-spike` (plan section 8 cleanup).

## 8. Reproducing and cleanup

```
python3 web-app/scripts/spike/measure.py selftest      # no Docker
web-app/scripts/spike/run.sh auto                      # M0 to M11 and the automated parts of M3, M5c, M7
web-app/scripts/spike/run.sh m12 10                    # M12, ten minutes at a 10 s interval
web-app/scripts/spike/run.sh skew                      # 11-minute mtime vs WSL clock sampling (no Docker)
web-app/scripts/spike/run.sh m3                        # 20 jittered WSL edits;  m11 re-records the illegal-character names
web-app/scripts/spike/run.sh assemble                  # rewrite the raw JSON from /mnt/d/sbw-spike/results
```

`web-app/scripts/spike/.env` is untracked: the root `.gitignore` entry `.env` matches
it (verified with `git check-ignore -v web-app/scripts/spike/.env`). Copy
`.env.example` to `.env` before the first run. The scratch folder
`/mnt/d/sbw-spike` is left in place for the operator steps; the operator
deletes it afterwards.

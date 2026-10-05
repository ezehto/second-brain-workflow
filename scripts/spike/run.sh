#!/usr/bin/env bash
# Mount spike runner (plan section 8). Everything it writes lives under
# /mnt/d/sbw-spike/ (results) or docs/spikes/ (the combined raw JSON).
#
#   run.sh auto             M0..M11 that need no human, plus automatable M3/M5c/M7 parts
#   run.sh m3 | m5c | m7 | m11   re-run one automated part (m3: M3_N edits, default 20, keys suffixed M3_SUFFIX)
#   run.sh skew [SECONDS]  sample Windows-mtime minus WSL clock every 1.5 s (default 660 s); no Docker
#   run.sh m12 INTERVAL     10-minute steady-state poll (M12) at INTERVAL seconds
#   run.sh all INTERVAL     auto, then m12
#   run.sh prep-operator    (re)create the files the Obsidian steps use
#   run.sh up | down        start / remove the probe containers
#   run.sh x ARGS...        run `measure.py ARGS` in the read-write probe
#   run.sh xro ARGS...      run `measure.py ARGS` in the read-only probe
#   run.sh save NAME        read JSON on stdin, store it as result NAME
#   run.sh assemble         write docs/spikes/phase-1-mount-spike-results.json
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SPIKE_ROOT=/mnt/d/sbw-spike
CORPUS="$SPIKE_ROOT/Spike Vault"
RESULTS="$SPIKE_ROOT/results"
RAW_JSON="$REPO/docs/spikes/phase-1-mount-spike-results.json"
ENVFILE="${ENVFILE:-$HERE/.env}"
M="$HERE/measure.py"
POLL_DURATION="${POLL_DURATION:-600}"
M3_SUFFIX="${M3_SUFFIX:-_jitter}"   # result-key suffix for the M3 WSL half
M3_N="${M3_N:-20}"                  # number of WSL edits

[ -f "$ENVFILE" ] || { echo "missing $ENVFILE: copy .env.example to .env" >&2; exit 1; }

dc() { docker compose -p sbwspike -f "$HERE/compose.spike.yml" --env-file "${ENVFILE_OVERRIDE:-$ENVFILE}" "$@"; }
px() { dc exec -T probe python /spike/measure.py "$@"; }
pr() { dc exec -T probe_ro python /spike/measure.py "$@"; }
save() { python3 "$M" save --dir "$RESULTS" --name "$1" >/dev/null; }                 # JSON on stdin
save_text() { python3 "$M" save --dir "$RESULTS" --name "$1" --text-file "$2" --rc "$3" >/dev/null; }
say() { printf '== %s\n' "$*" >&2; }

ensure_corpus() {
  mkdir -p "$RESULTS"
  [ -f "$CORPUS/.sbw-spike-scratch" ] || python3 "$HERE/gen_corpus.py" >&2
  [ -f "$RESULTS/.sbw-spike-scratch" ] || cp "$CORPUS/.sbw-spike-scratch" "$RESULTS/"
}

# Refuse to start containers unless the env file points at the scratch corpus (m8 does the same per form).
check_spike_path() {
  local svc src
  for svc in probe probe_ro; do
    src="$(dc config --format json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["'$svc'"]["volumes"][0]["source"])' 2>/dev/null)"
    [ "$src" = "$CORPUS" ] || { echo "refusing: SPIKE_PATH in $ENVFILE resolves to '${src:-<unresolved>}' for $svc, expected '$CORPUS'" >&2; exit 1; }
  done
}
up() { check_spike_path; dc up -d probe probe_ro >&2; }
down() { dc down --remove-orphans >&2; }

m0() {
  say M0 docker in WSL
  local t; t="$(mktemp)"
  { docker compose version; echo "-- rc=$?"; docker run --rm hello-world | head -5; echo "-- rc=${PIPESTATUS[0]}"; } >"$t" 2>&1
  local rc=0; grep -q 'Hello from Docker' "$t" || rc=1
  save_text M0 "$t" "$rc"; rm -f "$t"
}

# M8: for each .env form, ask compose what it resolves SPIKE_PATH to; only run a
# probe when it resolves to the scratch folder, so a wrong form cannot make Docker
# create a stray host directory.
m8() {
  say M8 space in path
  local out="$RESULTS/m8.tmp" forms_json="[]"
  python3 - "$RESULTS" <<'PY'
import sys
r = sys.argv[1]
open(f"{r}/env.unquoted", "w").write("SPIKE_PATH=/mnt/d/sbw-spike/Spike Vault\n")
open(f"{r}/env.double", "w").write('SPIKE_PATH="/mnt/d/sbw-spike/Spike Vault"\n')
open(f"{r}/env.single", "w").write("SPIKE_PATH='/mnt/d/sbw-spike/Spike Vault'\n")
PY
  : >"$out"
  for form in unquoted double single; do
    local ef="$RESULTS/env.$form" cfg src="" rc probe=""
    cfg="$(ENVFILE_OVERRIDE="$ef" dc config --format json 2>&1)"; rc=$?
    if [ $rc -eq 0 ]; then
      src="$(printf '%s' "$cfg" | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["probe"]["volumes"][0]["source"])' 2>&1)"
    fi
    if [ "$src" = "$CORPUS" ] && [ -d "$src" ]; then
      probe="$(ENVFILE_OVERRIDE="$ef" dc run --rm -T --no-deps probe python /spike/measure.py mounts 2>/dev/null)"
    fi
    python3 - "$form" "$rc" "$src" "$CORPUS" "$probe" "$cfg" >>"$out" <<'PY'
import json, sys
form, rc, src, corpus, probe, cfg = sys.argv[1:7]
print(json.dumps({"form": form, "config_rc": int(rc), "resolved_source": src, "matches_scratch_folder": src == corpus,
                  "probe": json.loads(probe) if probe else None, "config_error": cfg[:300] if int(rc) else None}))
PY
  done
  python3 - "$out" <<'PY' | save M8
import json, sys
forms = [json.loads(l) for l in open(sys.argv[1])]
ok = [f["form"] for f in forms if f["matches_scratch_folder"] and f["probe"] and f["probe"]["marker_present"] and f["probe"]["md_files"] >= 5000]
print(json.dumps({"measurement": "M8", "forms": forms, "working_forms": ok, "pass": bool(ok)}))
PY
  rm -f "$out"
}

# M11: create the names from the container, then look at them from Windows (PowerShell) and record the code points.
m11() {
  say M11 illegal characters, Windows view
  local ps="$RESULTS/m11.ps1" listing="$RESULTS/m11.listing.tmp" created="$RESULTS/m11.created.tmp"
  px illegal --keep >"$created"
  cat >"$ps" <<'PSEOF'
Get-ChildItem -LiteralPath 'D:\sbw-spike\Spike Vault\_m11' | ForEach-Object { ($_.Name.ToCharArray() | ForEach-Object { '{0:X4}' -f [int]$_ }) -join ' ' }
PSEOF
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w "$ps")" >"$listing" 2>&1
  python3 - "$created" "$listing" <<'PY' | save M11
import json, sys
d = json.load(open(sys.argv[1]))
d["windows_view_code_points"] = [l.strip() for l in open(sys.argv[2], errors="replace") if l.strip()]
d["windows_view_note"] = "PowerShell Get-ChildItem on D:\\sbw-spike\\Spike Vault\\_m11; U+F03A / U+F03F are private-use substitutes for : and ?"
print(json.dumps(d))
PY
  rm -rf "$CORPUS/_m11" "$ps" "$listing" "$created"
}

clock_offset() {
  python3 - "$HERE" <<'PY' | save clock
import json, subprocess, sys, time
vals = []
for _ in range(5):
    t0 = time.time()
    c = float(subprocess.run(["docker", "compose", "-p", "sbwspike", "-f", sys.argv[1] + "/compose.spike.yml", "exec", "-T", "probe",
                              "python", "-c", "import time; print(time.time())"], capture_output=True, text=True).stdout)
    t1 = time.time()
    vals.append(c - (t0 + t1) / 2)
print(json.dumps({"measurement": "clock", "container_minus_wsl_s": [round(v, 3) for v in vals], "note": "includes half the exec round trip"}))
PY
}

m3() {
  say "M3 $M3_N edits from WSL (gap 4 s + uniform 0..0.5 s)"
  mkdir -p "$CORPUS/_m3"
  local i; for i in 1 2 3 4 5; do printf -- '---\ntype: knowledge\n---\n\nwsl file %s\n' "$i" >"$CORPUS/_m3/wsl-$i.md"; done
  sleep 2   # let the baseline settle past the write cache
  local w="$RESULTS/m3.watch.tmp" err="$RESULTS/m3.err.tmp" files=() ; : >"$err"
  for i in 1 2 3 4 5; do files+=("_m3/wsl-$i.md"); done
  px watch --files "${files[@]}" --expect "$M3_N" --timeout $((M3_N * 5 + 30)) --interval 0.5 >"$w" 2>"$err" &
  local pid=$!
  for _ in $(seq 1 100); do grep -q ready "$err" && break; sleep 0.2; done
  python3 "$M" host-edit --root "$CORPUS" --files "${files[@]}" --n "$M3_N" --gap 4 --jitter 0.5 | tee "$RESULTS/m3.edits.tmp" | save "M3_wsl_edits$M3_SUFFIX"
  wait $pid
  save "M3_wsl_watch$M3_SUFFIX" <"$w"
  python3 "$M" latency --edits-json "@$RESULTS/m3.edits.tmp" --watch-json "@$w" | save "M3_wsl$M3_SUFFIX"
  rm -f "$w" "$err" "$RESULTS/m3.edits.tmp"
  rm -rf "$CORPUS/_m3"
}

m5c() {
  say M5c replace over a file locked by Windows
  mkdir -p "$CORPUS/_m5c"
  printf -- '---\ntype: knowledge\n---\n\nlocked file\n' >"$CORPUS/_m5c/target.md"
  local win log="$RESULTS/m5c.ps.tmp"; : >"$log"
  for _ in 1 2 3 4 5; do win="$(wslpath -w "$CORPUS/_m5c/target.md" 2>/dev/null)" && break; sleep 1; done   # drvfs can lag after a delete
  powershell.exe -NoProfile -Command "\$f=[System.IO.File]::Open('$win','Open','ReadWrite','Read'); Write-Output LOCKED; Start-Sleep 30; \$f.Close(); Write-Output RELEASED" >"$log" 2>&1 &
  local pid=$!
  for _ in $(seq 1 100); do grep -q LOCKED "$log" && break; sleep 0.2; done
  local locked=false control="" rep
  grep -q LOCKED "$log" && locked=true
  # control: with the lock held, does an append from WSL fail? proves the lock is effective
  control="$( { printf 'x\n' >>"$CORPUS/_m5c/target.md"; } 2>&1 && echo "append succeeded" )"
  if $locked; then
    rep="$(px replace --target _m5c/target.md 2>&1)"
  else
    rep='{"skipped": "lock was not acquired, replace not attempted"}'
  fi
  wait $pid 2>/dev/null   # let powershell release the lock before cleanup
  python3 - "$locked" "$control" "$rep" "$(cat "$log" | tr '\r\n' '  ')" <<'PY' | save M5c
import json, sys
locked, control, rep, log = sys.argv[1:5]
try:
    r = json.loads(rep)
except ValueError:
    r = {"unparsed": rep[-500:]}
print(json.dumps({"measurement": "M5c", "lock_held": locked == "true", "control_append_from_wsl": control or "(no output)",
                  "replace_result": r, "powershell_log": log}))
PY
  rm -f "$log"; rm -rf "$CORPUS/_m5c"
}

m7() {
  say M7 ownership and permissions
  local created st_wsl before after after_fm
  created="$(px create)"
  # shellcheck disable=SC2012
  st_wsl="$(stat -c '%U:%G %a %s' "$CORPUS/_m7/created-in-container.md")"
  (
    cd "$CORPUS/_m7" || exit 1
    git init -q . && git config core.filemode false && git config user.email spike@example.invalid && git config user.name spike
    git -c core.filemode=true add . && git -c core.filemode=true commit -q -m init
    printf 'edited from WSL\n' >>created-in-container.md
    printf 'status_filemode_false=%s\n' "$(git status --porcelain | tr '\n' '|')"
    printf 'status_filemode_true=%s\n' "$(git -c core.filemode=true status --porcelain | tr '\n' '|')"
  ) >"$RESULTS/m7.git.tmp" 2>&1
  local wsl_edit_rc
  printf 'second edit\n' >>"$CORPUS/_m7/created-in-container.md"; wsl_edit_rc=$?
  python3 - "$created" "$st_wsl" "$wsl_edit_rc" "$RESULTS/m7.git.tmp" <<'PY' | save M7_auto
import json, sys
created, st, rc, gitf = sys.argv[1:5]
git = dict(l.split("=", 1) for l in open(gitf).read().splitlines() if "=" in l)
print(json.dumps({"measurement": "M7_auto", "container_create": json.loads(created), "wsl_stat_owner_mode_size": st,
                  "wsl_printf_append_rc": int(rc), "git": git}))
PY
  rm -f "$RESULTS/m7.git.tmp"; rm -rf "$CORPUS/_m7"
}

prep_operator() {
  ensure_corpus; up
  mkdir -p "$CORPUS/_m3" "$CORPUS/_m5b"
  local i; for i in 1 2 3 4 5; do printf -- '---\ntype: knowledge\n---\n\nobsidian file %s\n' "$i" >"$CORPUS/_m3/obsidian-$i.md"; done
  printf -- '---\ntype: knowledge\n---\n\nreplace target for M5b\n' >"$CORPUS/_m5b/target.md"
  px create >/dev/null   # _m7/created-in-container.md, owned by the container uid
  (cd "$CORPUS/_m7" && rm -rf .git && git init -q . && git config core.filemode false && git config user.email spike@example.invalid \
     && git config user.name spike && git -c core.filemode=true add . && git -c core.filemode=true commit -q -m init)
  echo "operator files ready under $CORPUS (_m3, _m5b, _m7)" >&2
}

auto() {
  ensure_corpus
  m0; m8
  up; trap 'down' EXIT
  say mounts; px mounts | save mounts
  clock_offset
  say M1 scan; px scan | save M1; python3 "$M" scan --root "$CORPUS" | save M1_host_wsl
  say M2 hash; px hash | save M2
  say M4 mtime; px mtime | save M4
  say M5a replace; px replace --n 100 | save M5a
  say M9 read-only; pr rowrite | save M9
  say M10 case; px case | save M10
  m11
  m3
  m7
  m5c
  python3 "$M" assemble --dir "$RESULTS" --out "$RAW_JSON" >/dev/null
}

m12() {
  local interval="${1:?usage: run.sh m12 INTERVAL_SECONDS}"
  ensure_corpus; up
  say "M12 poll every ${interval}s for ${POLL_DURATION}s"
  local stats="$RESULTS/m12.stats.jsonl" cid; : >"$stats"
  cid="$(dc ps -q probe)"
  px poll --interval "$interval" --duration "$POLL_DURATION" >"$RESULTS/m12.poll.tmp" &
  local pid=$!
  while kill -0 $pid 2>/dev/null; do
    docker stats --no-stream --format '{{json .}}' "$cid" >>"$stats"
    sleep 10
  done
  wait $pid
  save M12_poll <"$RESULTS/m12.poll.tmp"
  python3 "$M" stats-summary --file "$stats" | save M12_stats
  rm -f "$RESULTS/m12.poll.tmp"
  python3 "$M" assemble --dir "$RESULTS" --out "$RAW_JSON" >/dev/null
}

case "${1:-}" in
  auto) auto ;;
  m12) shift; m12 "$@"; down ;;
  all) shift; auto; trap - EXIT; m12 "$@"; down ;;
  prep-operator) prep_operator ;;
  skew) ensure_corpus; python3 "$M" skew --root "$CORPUS" --duration "${2:-660}" --interval 1.5 | save skew; python3 "$M" assemble --dir "$RESULTS" --out "$RAW_JSON" >/dev/null ;;
  m3|m5c|m7|m11) ensure_corpus; up; trap 'down' EXIT; "$1"; python3 "$M" assemble --dir "$RESULTS" --out "$RAW_JSON" >/dev/null ;;
  up) up ;;
  down) down ;;
  x) shift; px "$@" ;;
  xro) shift; pr "$@" ;;
  save) shift; save "${1:?name}" ;;
  assemble) python3 "$M" assemble --dir "$RESULTS" --out "$RAW_JSON" ;;
  *) sed -n '2,15p' "$0"; exit 2 ;;
esac

#!/usr/bin/env bash
# Guard tests for scripts/e2e.sh (P1-19). Starts no containers: copies and `docker compose config` only.
set -uo pipefail

WEB_APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
E2E="$WEB_APP/scripts/e2e.sh"
EXAMPLE="$WEB_APP/.env.e2e.example"
ROOT=/mnt/d/sbw-e2e
T="$ROOT/test-$$"
TMP_BEFORE="$(find /tmp -maxdepth 1 -name 'tmp.*' | wc -l)"
mkdir -p "$T/src/.git" "$T/real"
echo note > "$T/src/note.md"; echo gitdata > "$T/src/.git/HEAD"
trap 'rm -rf "$T"' EXIT

FAILED=0
ok() { echo "ok: $*"; }
bad() { echo "FAIL: $*"; FAILED=1; }
check() { # check <description> <command...>: passes when the command succeeds
  local d="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "$d"; else bad "$d"; fi
}
# Env file derived from the example with lines appended (last assignment wins).
mkenv() { local f="$1"; shift; cp "$EXAMPLE" "$f"; local l; for l in "$@"; do echo "$l" >> "$f"; done; }
# run_e2e <env-file> <args...>: dry run against a test env file and a stand-in real vault.
run_e2e() { local e="$1"; shift; SBW_E2E_DRY_RUN=1 SBW_E2E_ENV_FILE="$e" SBW_E2E_REAL_VAULT="$T/real" "$E2E" "$@"; }
refused() { # refused <description> <env-file> <args...>: non-zero exit, a "refused:" message, no copy made
  local d="$1" e="$2"; shift 2
  local out rc=0
  out="$(run_e2e "$e" "$@" 2>&1)" || rc=$?
  if [ "$rc" -ne 0 ] && grep -q '^refused:' <<<"$out" && [ ! -e "$T/vault" ] && [ ! -e "$T/real/note.md" ]; then
    ok "$d"
  else bad "$d (rc=$rc: $out)"; fi
}

# Like refused, for a pre-existing vault directory: it must be left untouched.
refused_keep() {
  local d="$1" e="$2"; shift 2
  local out rc=0
  out="$(run_e2e "$e" "$@" 2>&1)" || rc=$?
  if [ "$rc" -ne 0 ] && grep -q '^refused:' <<<"$out" && [ -d "$T/vault/inner" ]; then ok "$d"
  else bad "$d (rc=$rc: $out)"; fi
}

# 1. Project name and vault path guards.
mkenv "$T/env.name" "COMPOSE_PROJECT_NAME=other" "VAULT_PATH=$T/vault"
refused "exits non-zero when the project name is not sbw-e2e" "$T/env.name" up
mkenv "$T/env.real" "VAULT_PATH=$T/real"
refused "exits non-zero when VAULT_PATH is the (overridden) real vault" "$T/env.real" up
mkenv "$T/env.inside" "VAULT_PATH=$T/real/sub"
refused "exits non-zero when VAULT_PATH is inside the real vault" "$T/env.inside" up
mkenv "$T/env.contains" "VAULT_PATH=$T"
refused "exits non-zero when VAULT_PATH contains the real vault" "$T/env.contains" up
mkenv "$T/env.out" "VAULT_PATH=/mnt/d/Projects/elsewhere"
refused "exits non-zero when VAULT_PATH is outside $ROOT/" "$T/env.out" up
mkenv "$T/env.dots" "VAULT_PATH=$T/x/../vault"
refused "exits non-zero when VAULT_PATH is not canonical (safe target via dot segments)" "$T/env.dots" up
ln -s "$T/real" "$T/link"
mkenv "$T/env.link" "VAULT_PATH=$T/link"
refused "exits non-zero when VAULT_PATH is a symlink to the real vault" "$T/env.link" up
mkenv "$T/env.case" "VAULT_PATH=/mnt/d/SBW-E2E/test-$$/real"
refused "exits non-zero when VAULT_PATH differs from the real vault only by letter case" "$T/env.case" up
mkenv "$T/env.default-real" "VAULT_PATH=/mnt/d/Second Brain"
if SBW_E2E_DRY_RUN=1 SBW_E2E_ENV_FILE="$T/env.default-real" "$E2E" up >/dev/null 2>&1; then
  bad "exits non-zero when VAULT_PATH is /mnt/d/Second Brain (no override)"
else ok "exits non-zero when VAULT_PATH is /mnt/d/Second Brain (no override)"; fi
if SBW_E2E_DRY_RUN=1 SBW_E2E_ENV_FILE="$T/env.default-real" SBW_E2E_REAL_VAULT="$T/real" "$E2E" up >/dev/null 2>&1; then
  bad "the real-vault override is additive: /mnt/d/Second Brain is still refused"
else ok "the real-vault override is additive: /mnt/d/Second Brain is still refused"; fi

# 2. Dotenv forms where Compose's parser and a naive reader disagree: every one must be refused, no copy.
mkenv "$T/env.b1" "VAULT_PATH=$T/vault" "export VAULT_PATH=$T/real"
refused "bypass: export VAULT_PATH=<real> after a good line" "$T/env.b1" up
mkenv "$T/env.b2" "VAULT_PATH=$T/vault" " VAULT_PATH=$T/real"
refused "bypass: leading space before VAULT_PATH=<real>" "$T/env.b2" up
mkenv "$T/env.b3" "VAULT_PATH=$T/vault" "VAULT_PATH = $T/real"
refused "bypass: VAULT_PATH = <real> with spaces around =" "$T/env.b3" up
mkenv "$T/env.b4" "VAULT_PATH=$T/real # $T/vault"
refused "bypass: VAULT_PATH=<real> # <comment naming a safe vault>" "$T/env.b4" up
mkenv "$T/env.b5" "X=../test-$$/real" "VAULT_PATH=$ROOT/\${X}"
refused "bypass: VAULT_PATH expanded from an earlier key with \${X}" "$T/env.b5" up
mkenv "$T/env.b6" "VAULT_PATH=$ROOT/vaultx\${SBWY}"
if SBWY=/../test-$$/real SBW_E2E_DRY_RUN=1 SBW_E2E_ENV_FILE="$T/env.b6" SBW_E2E_REAL_VAULT="$T/real" "$E2E" up >/dev/null 2>&1 \
   || [ -e "$T/vault" ] || [ -e "$ROOT/vaultx" ]; then
  bad "bypass: VAULT_PATH expanded from a shell-only variable"
else ok "bypass: VAULT_PATH expanded from a shell-only variable"; fi
mkenv "$T/env.b7" "VAULT_PATH=\"$T/real\""
refused "bypass: a quoted VAULT_PATH" "$T/env.b7" up

# 3. up with the golden vault copies it fresh.
mkenv "$T/env.good" "VAULT_PATH=$T/vault"
mkdir -p "$T/vault"; echo stale > "$T/vault/stale.txt"
out="$(run_e2e "$T/env.good" up 2>&1)"; rc=$?
check "up (golden) succeeds in dry run" test "$rc" -eq 0
check "up (golden) wipes the old vault directory" test ! -e "$T/vault/stale.txt"
check "up (golden) copies the golden vault" test -d "$T/vault/00-Inbox"
check "up (golden) leaves the test clock to the env file (no empty override)" bash -c '! grep -q "SECOND_BRAIN_TEST_MODE=" <<<"$1"' _ "$out"
check "the env file for the golden mode has SECOND_BRAIN_TEST_MODE=1 and SECOND_BRAIN_TODAY=2026-10-09" \
  bash -c 'grep -q "^SECOND_BRAIN_TEST_MODE=1$" "$1" && grep -q "^SECOND_BRAIN_TODAY=2026-10-09$" "$1"' _ "$EXAMPLE"
rm -rf "$T/vault"

# 4. --vault-copy-of.
refused "up --vault-copy-of with a missing source is refused" "$T/env.good" up --vault-copy-of "$T/nope"
mkdir -p "$T/linksrc"; ln -s "$T/src" "$T/linksrc/l"
refused "up --vault-copy-of a source containing a symlink is refused" "$T/env.good" up --vault-copy-of "$T/linksrc"
mkdir -p "$T/vault/inner"
refused_keep "up --vault-copy-of a source inside the e2e vault directory is refused" "$T/env.good" up --vault-copy-of "$T/vault/inner"
refused_keep "up --vault-copy-of a source containing the e2e vault directory is refused" "$T/env.good" up --vault-copy-of "$T"
rm -rf "$T/vault"
out="$(run_e2e "$T/env.good" up --vault-copy-of "$T/src" 2>&1)"; rc=$?
check "up --vault-copy-of a stand-in source succeeds in dry run" test "$rc" -eq 0
check "the copy contains the source files" test -f "$T/vault/note.md"
check "the copy excludes .git/" test ! -e "$T/vault/.git"
check "copy mode runs Compose with the two test-clock variables emptied" \
  grep -q 'DRYRUN: env SECOND_BRAIN_TEST_MODE= SECOND_BRAIN_TODAY= docker compose -p sbw-e2e ' <<<"$out"
rm -rf "$T/vault"
# The source may itself be the real-vault override: it is read, never mounted.
out="$(SBW_E2E_DRY_RUN=1 SBW_E2E_ENV_FILE="$T/env.good" SBW_E2E_REAL_VAULT="$T/src" "$E2E" up --vault-copy-of "$T/src" 2>&1)"; rc=$?
check "up --vault-copy-of succeeds when the source is also the real-vault override" test "$rc" -eq 0
check "the copy of the real-vault stand-in exists" test -f "$T/vault/note.md"

# What Compose renders for the copy run: only the copy is mounted; the clock variables are empty.
CFG="$(cd "$WEB_APP" && env SECOND_BRAIN_TEST_MODE= SECOND_BRAIN_TODAY= docker compose -p sbw-e2e --env-file "$T/env.good" -f docker-compose.yml -f docker-compose.e2e.yml --profile '*' config --format json 2>&1)"
check "docker compose config renders for the copy run" test -n "$CFG" -a "${CFG:0:1}" = "{"
MOUNTS="$(python3 -c '
import json, sys
for name, s in json.loads(sys.argv[1])["services"].items():
    for v in s.get("volumes", []):
        if v.get("type") == "bind":
            print(name, v["source"], v["target"])
' "$CFG" 2>/dev/null)"
check "rendered config mounts the copy at /vault" grep -qx "backend $T/vault /vault" <<<"$MOUNTS"
check "rendered config never mounts the source path" bash -c '! grep -q "$1" <<<"$2"' _ "$T/src" "$MOUNTS"
check "rendered config never mounts /mnt/d/Second Brain" bash -c '! grep -q "Second Brain" <<<"$1"' _ "$MOUNTS"
check "rendered backend has empty SECOND_BRAIN_TEST_MODE and SECOND_BRAIN_TODAY in copy mode" python3 -c '
import json, sys
e = json.loads(sys.argv[1])["services"]["backend"]["environment"]
sys.exit(0 if e["SECOND_BRAIN_TEST_MODE"] == "" and e["SECOND_BRAIN_TODAY"] == "" else 1)' "$CFG"
check "rendered backend has no env_file (the real .env is not read)" python3 -c '
import json, sys
sys.exit(1 if "env_file" in json.loads(sys.argv[1])["services"]["backend"] else 0)' "$CFG"
check "rendered project name and volumes are sbw-e2e" python3 -c '
import json, sys
c = json.loads(sys.argv[1])
sys.exit(0 if c["name"] == "sbw-e2e" and all(v["name"].startswith("sbw-e2e_") for v in c["volumes"].values()) else 1)' "$CFG"
GCFG="$(cd "$WEB_APP" && docker compose -p sbw-e2e --env-file "$T/env.good" -f docker-compose.yml -f docker-compose.e2e.yml config --format json 2>&1)"
check "rendered backend has the pinned clock in golden mode" python3 -c '
import json, sys
e = json.loads(sys.argv[1])["services"]["backend"]["environment"]
sys.exit(0 if e["SECOND_BRAIN_TEST_MODE"] == "1" and e["SECOND_BRAIN_TODAY"] == "2026-10-09" else 1)' "$GCFG"
rm -rf "$T/vault"

# 5. user composes createsuperuser --noinput with the password only via -e.
out="$(E2E_PASSWORD=s3cret-test-value run_e2e "$T/env.good" user 2>&1)"; rc=$?
check "user succeeds in dry run" test "$rc" -eq 0
check "user command contains createsuperuser --noinput" grep -q 'createsuperuser --noinput' <<<"$out"
check "user passes DJANGO_SUPERUSER_PASSWORD via -e" grep -q -e '-e DJANGO_SUPERUSER_PASSWORD' <<<"$out"
check "user does not print the password value" bash -c '! grep -q s3cret-test-value <<<"$1"' _ "$out"
check "user targets only the sbw-e2e project" grep -q 'docker compose -p sbw-e2e ' <<<"$out"
check "no file under web-app contains the test password" bash -c '! grep -rqs s3cret-test-value "$1" --exclude-dir=node_modules --exclude-dir=.git --exclude=test_e2e_guard.sh' _ "$WEB_APP"

# 6. down -v is scoped to the sbw-e2e project.
out="$(run_e2e "$T/env.good" down -v 2>&1)"
check "down -v composes 'docker compose -p sbw-e2e ... down -v'" grep -q 'docker compose -p sbw-e2e .* down -v' <<<"$out"

# 7. --help.
check "--help does not print the shell options line" bash -c '! "$1" --help | grep -q "set -euo"' _ "$E2E"

# 8. No temporary directories left behind.
rm -rf "$T"
TMP_AFTER="$(find /tmp -maxdepth 1 -name 'tmp.*' | wc -l)"
check "no /tmp/tmp.* directories left behind ($TMP_BEFORE before, $TMP_AFTER after)" test "$TMP_BEFORE" -eq "$TMP_AFTER"
exit "$FAILED"

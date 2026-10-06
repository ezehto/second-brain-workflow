#!/usr/bin/env bash
# Static Compose check (P1-16). Run from anywhere; it checks whichever services
# exist in web-app/docker-compose.yml, so later tasks re-run it unchanged.
set -euo pipefail

WEB_APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$WEB_APP/.." && pwd)"
cd "$WEB_APP"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "ok: $*"; }

[ -f docker-compose.yml ] || fail "web-app/docker-compose.yml is missing"
[ -f .env.example ] || fail "web-app/.env.example is missing"

# Use .env when present; on a fresh clone fall back to .env.example.
[ -z "${COMPOSE_FILE:-}" ] || fail "COMPOSE_FILE is set; unset it so only docker-compose.yml is checked and run"
ENVFILE=.env
[ -f .env ] || ENVFILE=.env.example

ERR="$(mktemp)"
trap 'rm -f "$ERR"' EXIT
compose() { docker compose --env-file "$ENVFILE" --profile '*' "$@"; }

JSON="$(compose config --format json 2>"$ERR")" || fail "docker compose config does not parse: $(cat "$ERR")"
[ ! -s "$ERR" ] || fail "docker compose config warned: $(cat "$ERR")"
VARS="$(compose config --variables --format json 2>"$ERR")" || fail "docker compose config --variables failed: $(cat "$ERR")"
ok "docker compose config parses with no warnings (env file: $ENVFILE)"

# VAULT_PATH as Compose resolves it (env file, `export` form, or the shell), unquoted.
ENVOUT="$(compose config --environment 2>"$ERR")" || fail "docker compose config --environment failed: $(cat "$ERR")"
VAULT_PATH="$(printf '%s\n' "$ENVOUT" | sed -n 's/^VAULT_PATH=//p' | tail -n1)"

# Rules evaluated generically over every rendered service.
JSON="$JSON" VARS="$VARS" VAULT_PATH="$VAULT_PATH" python3 - <<'PY' || exit 1
import json, os, re, sys

services = json.loads(os.environ["JSON"]).get("services", {})
vault = os.environ["VAULT_PATH"]
vault_real = os.path.realpath(vault) if vault else None
forbidden = {"SECOND_BRAIN_TEST_MODE", "SECOND_BRAIN_TODAY"}
problems = []

def is_vault(v):
    src = v.get("source")
    return v.get("target") == "/vault" or bool(
        vault_real and src and os.path.realpath(src) == vault_real)

for name, svc in services.items():
    for p in svc.get("ports", []):
        if p.get("host_ip") != "127.0.0.1":
            problems.append(f"{name}: port {p.get('published')} binds {p.get('host_ip') or 'all interfaces'}, not 127.0.0.1")
    if name == "db" and svc.get("ports"):
        problems.append("db publishes a port")
    mode = svc.get("network_mode", "")
    if mode and not mode.startswith("service:"):
        problems.append(f"{name}: network_mode '{mode}' bypasses the 127.0.0.1 port rule")
    for v in svc.get("volumes", []):
        if is_vault(v):
            if name == "test":
                problems.append("test mounts the vault")
            if name == "indexer" and not v.get("read_only"):
                problems.append("indexer vault mount is not :ro")
    if name not in ("test", "e2e"):
        for k in forbidden & set(svc.get("environment") or {}):
            problems.append(f"{name}: environment sets {k}")

example = {m.group(1) for line in open(".env.example")
           if (m := re.match(r"\s*(?:export\s+)?([A-Za-z_]\w*)\s*[=:]", line))}
for var in sorted(set(json.loads(os.environ["VARS"])) - example):
    problems.append(f".env.example lacks {var}, referenced in docker-compose.yml")

def words(v):
    return [v] if isinstance(v, str) else list(v or [])

for name, svc in services.items():
    for key in ("command", "entrypoint"):
        if any("createsuperuser" in w for w in words(svc.get(key))):
            problems.append(f"{name}: {key} runs createsuperuser")

dockerfile = open("backend/Dockerfile").read()
for line in dockerfile.splitlines():
    if re.match(r"\s*(CMD|ENTRYPOINT)\b", line) and "createsuperuser" in line:
        problems.append(f"backend/Dockerfile: {line.strip()}")

if problems:
    print("\n".join("FAIL: " + p for p in problems), file=sys.stderr)
    sys.exit(1)
print("ok: every published port binds 127.0.0.1")
print("ok: db publishes no port")
print("ok: no service uses host or other non-service network_mode")
print("ok: indexer vault mount (if any) is read-only")
print("ok: test service (if any) does not mount the vault")
print("ok: test-mode variables are absent from every non-test service")
print("ok: no service command or entrypoint, and no backend Dockerfile CMD or ENTRYPOINT, creates a user")
print("ok: .env.example defines every variable referenced in docker-compose.yml")
print("ok: services checked: " + ", ".join(sorted(services)))
PY

git -C "$REPO" check-ignore -q web-app/.env || fail "web-app/.env is not gitignored"
ok ".env is gitignored"

# Test-mode switches must never be set in a real environment file (plan 2.12).
for f in .env.example .env; do
  [ -f "$f" ] || continue
  if grep -qE '^[[:space:]]*(export[[:space:]]+)?(SECOND_BRAIN_TEST_MODE|SECOND_BRAIN_TODAY)[[:space:]]*[=:]' "$f"; then
    fail "$f sets SECOND_BRAIN_TEST_MODE or SECOND_BRAIN_TODAY"
  fi
done
ok "no env file sets SECOND_BRAIN_TEST_MODE or SECOND_BRAIN_TODAY"

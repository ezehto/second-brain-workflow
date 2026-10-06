#!/usr/bin/env bash
# CSRF through the Vite proxy (P1-31, review S-15): proves with curl, against the e2e stack's frontend
# port, that the cookie, the header and the Origin check all survive the proxy.
#
#   E2E_PASSWORD=... scripts/check_csrf_proxy.sh
#
# Start the stack first: `scripts/e2e.sh up`, then `E2E_PASSWORD=... scripts/e2e.sh user` with the same
# password (E2E_USERNAME defaults to e2e). Checks, each printed as an `ok:` line:
#   1. GET /api/auth/csrf/ gives 204 and a csrftoken cookie
#   2. login with the cookie and X-CSRFToken, from the frontend's own origin, gives 200
#   3. login without the X-CSRFToken header gives 403
#   4. login with the header but Origin: http://evil.example gives 403
# Any mismatch prints FAIL and exits 1. It refuses to run against the real stack (port 5173, or the
# FRONTEND_PORT of web-app/.env), because it logs in.
set -euo pipefail
export LC_ALL=C

WEB_APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WEB_APP"

die() { echo "refused: $*" >&2; exit 2; }
fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "ok: $*"; }
env_get() { [ -f "$2" ] && sed -n "s/^$1=//p" "$2" | tail -n1 || true; }

E2E_ENV=.env.e2e
[ -f "$E2E_ENV" ] || E2E_ENV=.env.e2e.example
PORT="${CSRF_PROXY_PORT:-$(env_get FRONTEND_PORT "$E2E_ENV")}"
PORT="${PORT:-5174}"
REAL_PORT="$(env_get FRONTEND_PORT .env)"
# Strip quotes, spaces and a CR so `"5173"` or `5173\r` compare as 5173.
clean() { printf '%s' "$1" | tr -d "\"' \r"; }
PORT="$(clean "$PORT")"
REAL_PORT="$(clean "$REAL_PORT")"
case "$PORT" in ''|*[!0-9]*) die "port '$PORT' is not a number" ;; esac
# 05173 is 5173: compare as decimal numbers, not strings.
PORT=$((10#$PORT))
case "$REAL_PORT" in *[!0-9]*) die "FRONTEND_PORT '$REAL_PORT' in .env is not a number" ;; esac
[ -z "$REAL_PORT" ] || REAL_PORT=$((10#$REAL_PORT))
[ "$PORT" != 5173 ] || die "port 5173 is the real stack's frontend; this script logs in and runs against the e2e stack only"
[ -z "$REAL_PORT" ] || [ "$PORT" != "$REAL_PORT" ] || die "port $PORT is the real stack's FRONTEND_PORT in .env"

USERNAME="${E2E_USERNAME:-e2e}"
[ -n "${E2E_PASSWORD:-}" ] || die "set E2E_PASSWORD to the password given to 'scripts/e2e.sh user'"

BASE="http://127.0.0.1:$PORT"
ORIGIN="$BASE"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

curl -fsS -o /dev/null "$BASE/api/health/" 2>/dev/null || fail "$BASE/api/health/ is not answering: is the e2e stack up (scripts/e2e.sh up)?"

# The csrftoken cookie value in a Netscape cookie jar (HttpOnly lines carry a #HttpOnly_ prefix).
token_of() { awk '$6 == "csrftoken" { print $7 }' "$1" | tail -n1; }
# The login body, built by python so no password character needs shell quoting; never in argv.
body() { USERNAME="$USERNAME" python3 -c 'import json, os, sys; sys.stdout.write(json.dumps({"username": os.environ["USERNAME"], "password": os.environ["E2E_PASSWORD"]}))'; }
# login <jar> [curl args...]: prints the HTTP status of POST /api/auth/login/.
login() {
  local jar="$1"; shift
  body | curl -sS -o /dev/null -w '%{http_code}' -b "$jar" -c "$jar" -X POST \
    -H 'Content-Type: application/json' --data-binary @- "$@" "$BASE/api/auth/login/"
}
fresh_jar() { # fresh_jar <file>: a jar holding a new csrftoken, via the proxy
  local status
  status="$(curl -sS -o /dev/null -w '%{http_code}' -c "$1" "$BASE/api/auth/csrf/" || true)"
  [ "$status" = 204 ] || fail "GET /api/auth/csrf/ returned $status, expected 204"
  [ -n "$(token_of "$1")" ] || fail "GET /api/auth/csrf/ set no csrftoken cookie"
}

# 1. The cookie is set through the proxy.
JAR1="$TMP/jar1"
fresh_jar "$JAR1"
ok "GET /api/auth/csrf/ through port $PORT returned 204 and set the csrftoken cookie"

# 2. Cookie plus header, same-origin: accepted.
status="$(login "$JAR1" -H "X-CSRFToken: $(token_of "$JAR1")" -H "Origin: $ORIGIN" || true)"
[ "$status" = 200 ] || fail "login with cookie and X-CSRFToken returned $status, expected 200 (is the user '$USERNAME' created with this E2E_PASSWORD?)"
ok "login with the csrftoken cookie and X-CSRFToken header returned 200"

# 3. Cookie without the header: rejected.
JAR2="$TMP/jar2"
fresh_jar "$JAR2"
status="$(login "$JAR2" -H "Origin: $ORIGIN" || true)"
[ "$status" = 403 ] || fail "login without X-CSRFToken returned $status, expected 403"
ok "login without the X-CSRFToken header returned 403"

# 4. Header and cookie but a foreign Origin: rejected.
JAR3="$TMP/jar3"
fresh_jar "$JAR3"
status="$(login "$JAR3" -H "X-CSRFToken: $(token_of "$JAR3")" -H "Origin: http://evil.example" || true)"
[ "$status" = 403 ] || fail "login with Origin http://evil.example returned $status, expected 403"
ok "login with the header but Origin http://evil.example returned 403"

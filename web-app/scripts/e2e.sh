#!/usr/bin/env bash
# E2E stack (P1-19): start, seed and stop the separate Compose project "sbw-e2e".
#
#   scripts/e2e.sh up [--vault-copy-of <path>]   fresh vault copy, start db/backend/frontend, migrate
#   scripts/e2e.sh user                          create the e2e superuser (createsuperuser --noinput)
#   scripts/e2e.sh down [-v]                     stop; -v also removes the sbw-e2e volumes
#
# `up` copies the golden vault into VAULT_PATH (under /mnt/d/sbw-e2e/) and runs with the pinned test
# clock from .env.e2e. `up --vault-copy-of <path>` copies <path> instead (excluding .git/; the source is
# read, never mounted; symlinks in it are refused) and runs with SECOND_BRAIN_TEST_MODE and
# SECOND_BRAIN_TODAY empty (unset), so the copy is checked at the real date. `user` takes
# E2E_USERNAME (default e2e), E2E_EMAIL and E2E_PASSWORD (default: generated and printed once).
# Before anything runs, the script lints the env file and checks the /vault bind mounts that Compose
# actually renders: the real vault (/mnt/d/Second Brain) can never be mounted.
# Test hooks: SBW_E2E_ENV_FILE, SBW_E2E_REAL_VAULT (an extra "real vault" to refuse),
# SBW_E2E_DRY_RUN=1 (print the compose commands that would change anything, run none of them).
set -euo pipefail
export LC_ALL=C

WEB_APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$WEB_APP/.." && pwd)"
cd "$WEB_APP"

PROJECT=sbw-e2e
E2E_ROOT=/mnt/d/sbw-e2e
GOLDEN="$REPO/second-brain/fixtures/golden-vault/vault"
ENV_FILE="${SBW_E2E_ENV_FILE:-.env.e2e}"
DRY_RUN="${SBW_E2E_DRY_RUN:-0}"

die() { echo "refused: $*" >&2; exit 2; }
usage() { sed -n '2,/^set -e/p' "${BASH_SOURCE[0]}" | sed '$d; s/^# \{0,1\}//'; exit "${1:-2}"; }

# Value of KEY in a dotenv file that already passed lint_env: last assignment wins.
env_get() { sed -n "s/^$1=//p" "$2" | tail -n1; }

# True when A is B or inside B, comparing by path and, for existing paths, by identity (-ef), so a
# different letter case on drvfs, a symlink or a bind alias cannot slip through.
within() {
  local p="$1"
  while :; do
    [ "$p" = "$2" ] && return 0
    if [ -e "$p" ] && [ -e "$2" ] && [ "$p" -ef "$2" ]; then return 0; fi
    [ "$p" = / ] && return 1
    p="$(dirname -- "$p")"
  done
}

# --- Arguments ----------------------------------------------------------------------------------
sub="${1:-}"; [ $# -eq 0 ] || shift
COPY_SRC=""
case "$sub" in
  up)
    if [ "${1:-}" = --vault-copy-of ]; then
      [ -n "${2:-}" ] && [ $# -eq 2 ] || usage
      [ -d "$2" ] || die "--vault-copy-of source does not exist or is not a directory: $2"
      COPY_SRC="$(realpath -- "$2")"
    elif [ $# -gt 0 ]; then usage; fi ;;
  user) [ $# -eq 0 ] || usage ;;
  down) case "${1:-}" in -v|"") [ $# -le 1 ] || usage ;; *) usage ;; esac ;;
  -h|--help|help) usage 0 ;;
  *) usage ;;
esac

# --- Environment ----------------------------------------------------------------------------------
# Stop the caller's shell from overriding the env file during Compose interpolation.
unset COMPOSE_PROJECT_NAME COMPOSE_FILE COMPOSE_PROFILES COMPOSE_ENV_FILES
while IFS= read -r k; do unset "$k"; done < <(sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' .env.e2e.example)

if [ ! -f "$ENV_FILE" ]; then
  [ "$ENV_FILE" = .env.e2e ] || die "env file $ENV_FILE does not exist"
  cp .env.e2e.example .env.e2e
  echo "created .env.e2e from .env.e2e.example"
fi

# Strict lint: only plain KEY=value lines. Compose's dotenv parser also accepts `export`, spaces,
# quotes, trailing comments and ${VAR} expansion, which would let the value Compose uses differ from
# the one checked here.
lint_re='^[A-Z_][A-Z0-9_]*=[^$"'\''\]*$'
n=0
while IFS= read -r line || [ -n "$line" ]; do
  n=$((n + 1))
  [[ "$line" =~ ^[[:space:]]*$ || "$line" =~ ^[[:space:]]*# ]] && continue
  [[ "$line" =~ $lint_re ]] || die "$ENV_FILE line $n is not a plain KEY=value line (no export, spaces around =, quotes, \$ or backslash): $line"
done < "$ENV_FILE"

# --- Compose invocation -------------------------------------------------------------------------
ENVPFX=()
# Copy mode: the shell wins over --env-file, so empty values here unset the pinned clock.
[ -z "$COPY_SRC" ] || ENVPFX=(env SECOND_BRAIN_TEST_MODE= SECOND_BRAIN_TODAY=)
dc() { "${ENVPFX[@]}" docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.e2e.yml "$@"; }
compose() {
  if [ "$DRY_RUN" = 1 ]; then
    echo "DRYRUN: ${ENVPFX[*]} docker compose -p $PROJECT --env-file $ENV_FILE -f docker-compose.yml -f docker-compose.e2e.yml $*"
  else
    dc "$@"
  fi
}

# --- Guards: checked before anything runs -------------------------------------------------------
[ "$(env_get COMPOSE_PROJECT_NAME "$ENV_FILE")" = "$PROJECT" ] \
  || die "COMPOSE_PROJECT_NAME in $ENV_FILE must be exactly $PROJECT"

REAL_VAULTS=("$(realpath -m -- "/mnt/d/Second Brain")")
[ -z "${SBW_E2E_REAL_VAULT:-}" ] || REAL_VAULTS+=("$(realpath -m -- "$SBW_E2E_REAL_VAULT")")

check_vault_path() { # a path the stack would mount or wipe
  local p="$1" r
  [ -n "$p" ] || die "vault path is empty"
  [ "$p" = "$(realpath -m -- "$p")" ] || die "vault path must be canonical ($p resolves to $(realpath -m -- "$p"))"
  case "$p" in "$E2E_ROOT"/?*) ;; *) die "vault path must be under $E2E_ROOT/ (got $p)" ;; esac
  if [ -e "$p" ] && [ "$p" -ef "$E2E_ROOT" ]; then die "vault path is the e2e root"; fi
  for r in "${REAL_VAULTS[@]}"; do
    within "$p" "$r" && die "vault path $p is, or is inside, the real vault $r"
    within "$r" "$p" && die "vault path $p contains the real vault $r"
  done
  return 0
}

VAULT="$(env_get VAULT_PATH "$ENV_FILE")"
check_vault_path "$VAULT"

# What Compose will really mount at /vault, for every service, profiles included.
RENDERED="$(dc --profile '*' config --format json 2>&1)" || die "docker compose config failed: $RENDERED"
SOURCES="$(RENDERED="$RENDERED" python3 -c '
import json, os
for svc in json.loads(os.environ["RENDERED"]).get("services", {}).values():
    for v in svc.get("volumes", []):
        if v.get("target") == "/vault":
            print(v.get("source", ""))
')" || die "could not read the rendered Compose configuration"
[ -n "$SOURCES" ] || die "rendered Compose configuration has no /vault mount"
while IFS= read -r src; do
  check_vault_path "$src"
  [ "$src" = "$VAULT" ] || die "Compose mounts $src at /vault but VAULT_PATH is $VAULT"
done <<<"$SOURCES"

cmd_up() {
  local src="$GOLDEN"
  if [ -n "$COPY_SRC" ]; then
    src="$COPY_SRC"
    within "$VAULT" "$src" && die "source $src contains or is the e2e vault directory"
    within "$src" "$VAULT" && die "source $src is inside the e2e vault directory"
    echo "note: running with SECOND_BRAIN_TEST_MODE and SECOND_BRAIN_TODAY empty (real date)"
  fi
  [ -d "$src" ] || die "source vault not found: $src"
  [ -z "$(find "$src" -type l -print -quit)" ] || die "source $src contains symlinks: $(find "$src" -type l -print -quit)"

  check_vault_path "$VAULT"
  rm -rf --one-file-system -- "$VAULT"
  mkdir -p -- "$VAULT"
  tar -C "$src" --exclude=./.git -cf - . | tar -C "$VAULT" -xf -
  echo "vault copy: $src -> $VAULT"

  compose up -d --wait db
  compose up -d backend frontend
  compose exec -T backend python manage.py migrate --noinput
  local port; port="$(env_get BACKEND_PORT "$ENV_FILE")"
  if [ "$DRY_RUN" != 1 ]; then
    local healthy=0
    for _ in $(seq 1 30); do
      if curl -fsS "http://127.0.0.1:$port/api/health/" >/dev/null 2>&1; then healthy=1; break; fi
      sleep 1
    done
    [ "$healthy" = 1 ] || die "backend not healthy after 30 s"
  fi
  echo "e2e stack up. health: http://127.0.0.1:$port/api/health/"
  echo "frontend:     http://127.0.0.1:$(env_get FRONTEND_PORT "$ENV_FILE")/"
}

cmd_user() {
  local user="${E2E_USERNAME:-e2e}" pw="${E2E_PASSWORD:-}" generated=0
  if [ -z "$pw" ]; then
    pw="$(head -c 24 /dev/urandom | base64 | tr -d '+/=\n')"
    generated=1
  fi
  # The password is exported for this one command only and passed by name (-e NAME), so it
  # appears in no file and not in the process arguments.
  DJANGO_SUPERUSER_PASSWORD="$pw" compose exec -T \
    -e "DJANGO_SUPERUSER_USERNAME=$user" -e "DJANGO_SUPERUSER_EMAIL=${E2E_EMAIL:-e2e@example.invalid}" \
    -e DJANGO_SUPERUSER_PASSWORD \
    backend python manage.py createsuperuser --noinput
  echo "e2e user: $user"
  if [ "$generated" = 1 ]; then echo "e2e password (shown once): $pw"; fi
}

cmd_down() {
  # Named volumes are scoped by project (sbw-e2e_*), so -v cannot touch the real web-app_* volumes.
  # --profile '*' so profiled services (indexer, test, e2e) started by hand come down too.
  compose --profile '*' down "$@"
}

case "$sub" in
  up) cmd_up ;;
  user) cmd_user ;;
  down) cmd_down "$@" ;;
esac

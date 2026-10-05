#!/usr/bin/env bash
# Install or remove the second-brain skill and slash commands in a Claude Code
# config directory (default ~/.claude).
#
#   install.sh [--target DIR] [--dry-run] [--force]      install or update (by copy)
#   install.sh --uninstall [--target DIR] [--dry-run] [--force]
#
# Installs <script dir>/skills/second-brain/** and <script dir>/commands/*.md.
# Every file under the skill directory ships, dotfiles included.
#
# The script records every file it installs (with a sha256) and every directory
# it creates in DIR/.second-brain-manifest, and only ever modifies or deletes
# what that manifest lists. Anything else in DIR (CLAUDE.md, settings.json,
# docs/, other skills and commands) is never touched.
#
# If an installed file was edited, or replaced by a symlink or a directory, the
# run is refused with nothing changed. --force overwrites or removes such files
# (a symlink is removed itself, never followed; a directory only if empty).
# After an interrupted update, files can look modified although nobody edited
# them; re-running install, or using --force, resolves it.
# A symlinked parent directory is always refused.
#
# After an uninstall that left user files behind, a reinstall does not re-own
# the surviving directories, so a later uninstall leaves them in place.
#
# Manifest (v2): first line "# second-brain install manifest v2", then one entry
# per line: "D <relative path>" for a directory this script created and
# "F <sha256> <relative path>" for an installed file. Any other header is refused.

# shellcheck disable=SC2034  # arrays handed to write_manifest are read through namerefs
set -euo pipefail
unset CDPATH

if [ -z "${BASH_VERSINFO:-}" ] || [ "${BASH_VERSINFO[0]}" -lt 4 ] ||
  { [ "${BASH_VERSINFO[0]}" -eq 4 ] && [ "${BASH_VERSINFO[1]}" -lt 4 ]; }; then
  echo "install.sh: needs bash 4.4 or newer (associative arrays, namerefs, mapfile)" >&2
  exit 1
fi

MANIFEST_NAME=".second-brain-manifest"
HEADER_V2="# second-brain install manifest v2"
SELF="${BASH_SOURCE[0]}"
SRC_ROOT="$(cd -P -- "$(dirname -- "$SELF")" >/dev/null && pwd -P)"

die() { echo "install.sh: $*" >&2; exit 1; }

target=""
mode=install
dry_run=0
force=0
while [ $# -gt 0 ]; do
  case "$1" in
    --target)
      [ $# -ge 2 ] && [ -n "$2" ] || die "--target needs a directory"
      target="$2"; shift 2 ;;
    --uninstall) mode=uninstall; shift ;;
    --dry-run) dry_run=1; shift ;;
    --force) force=1; shift ;;
    -h|--help)
      awk 'NR==1 {next} /^#/ {sub(/^# ?/, ""); print; next} {exit}' "$SELF"
      exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

if [ -z "$target" ]; then
  case "${HOME:-}" in
    /*) target="$HOME/.claude" ;;
    *) die "HOME is not an absolute path; use --target" ;;
  esac
fi

# Resolve the target physically; it may itself be a symlink (e.g. a dotfiles
# setup), which is fine because the user named it. Everything below it is checked.
if [ -e "$target" ]; then
  [ -d "$target" ] || die "target is not a directory: $target"
  target="$(cd -P -- "$target" >/dev/null && pwd -P)"
else
  [ "$mode" = install ] || die "target does not exist: $target"
  case "$target" in /*) ;; *) target="$PWD/$target" ;; esac
fi
[ "$target" != "/" ] || die "refusing to use / as the target"
MANIFEST="$target/$MANIFEST_NAME"

say() { if [ "$dry_run" = 1 ]; then echo "[dry-run] $*"; else echo "$*"; fi; }

TMPFILES=()
cleanup() { [ ${#TMPFILES[@]} -eq 0 ] || rm -f -- "${TMPFILES[@]}"; }
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

# Hash from stdin so no file name (which may contain a backslash) is printed.
hash_of() {
  local h
  h="$(sha256sum < "$1")" || return 1
  h="${h%% *}"
  [[ "$h" =~ ^[0-9a-f]{64}$ ]] || return 1
  printf '%s' "$h"
}

# --- path validation ---------------------------------------------------------

parts=()
split_path() { local IFS=/; read -r -a parts <<<"$1"; }

valid_rel() { # $1 = kind (F|D), $2 = relative path
  local kind="$1" p="$2" part
  [[ "$p" =~ [[:cntrl:]] ]] && return 1
  [ -n "$p" ] || return 1
  case "$p" in /*|*/) return 1 ;; esac
  split_path "$p"
  for part in "${parts[@]}"; do
    case "$part" in ""|"."|"..") return 1 ;; esac
  done
  case "$kind:$p" in
    F:skills/second-brain/*) return 0 ;;
    F:commands/*/*) return 1 ;;
    F:commands/?*.md) return 0 ;;
    D:skills|D:commands|D:skills/second-brain|D:skills/second-brain/*) return 0 ;;
    *) return 1 ;;
  esac
}

# Fail if an existing component under the target is a symlink. With "parents"
# the final component is not examined (used for files, whose leaf is classified
# separately). Splitting never globs.
no_symlink_in_path() { # $1 = relative path, $2 = "parents" to skip the leaf
  local cur="$target" i n
  split_path "$1"
  n=${#parts[@]}
  [ "${2:-}" != parents ] || n=$((n-1))
  for ((i=0; i<n; i++)); do
    cur="$cur/${parts[i]}"
    if [ -L "$cur" ]; then return 1; fi
    [ -e "$cur" ] || return 0
  done
  return 0
}

# --- manifest ----------------------------------------------------------------

declare -A old_files=() old_dirs=() new_hash=()
old_file_list=() old_dir_list=()

load_manifest() {
  [ -e "$MANIFEST" ] || [ -L "$MANIFEST" ] || return 0
  [ -f "$MANIFEST" ] && [ ! -L "$MANIFEST" ] || die "manifest is not a regular file: $MANIFEST"
  local line kind path hash first=1
  while IFS= read -r line || [ -n "$line" ]; do
    if [ "$first" = 1 ]; then
      [ "$line" = "$HEADER_V2" ] || die "unrecognised manifest header in $MANIFEST"
      first=0; continue
    fi
    hash=""
    if [[ "$line" =~ ^D\ (.+)$ ]]; then
      kind=D; path="${BASH_REMATCH[1]}"
    elif [[ "$line" =~ ^F\ ([0-9a-f]{64})\ (.+)$ ]]; then
      kind=F; hash="${BASH_REMATCH[1]}"; path="${BASH_REMATCH[2]}"
    else
      die "bad manifest line: $line"
    fi
    valid_rel "$kind" "$path" || die "manifest lists a path outside the install area: $path"
    no_symlink_in_path "$path" parents || die "manifest path passes through a symlink: $path"
    if [ "$kind" = F ]; then
      [ -n "${old_files[$path]+x}" ] || old_file_list+=("$path")
      old_files[$path]="$hash"
    else
      [ -n "${old_dirs[$path]+x}" ] || { old_dirs[$path]=1; old_dir_list+=("$path"); }
    fi
  done < "$MANIFEST"
  [ "$first" = 0 ] || die "empty manifest: $MANIFEST"
}

write_manifest() { # args: names of the files array, dirs array, hash map
  local -n _f="$1" _d="$2" _h="$3"
  local tmp p
  tmp="$(mktemp "$target/.second-brain-manifest.XXXXXX")"
  TMPFILES+=("$tmp")
  {
    echo "$HEADER_V2"
    for p in "${_d[@]}"; do echo "D $p"; done
    for p in "${_f[@]}"; do echo "F ${_h[$p]} $p"; done
  } > "$tmp"
  chmod 644 "$tmp"
  mv -fT -- "$tmp" "$MANIFEST"
}

sort_dirs_shallow_first() {
  awk '{ n=gsub("/","/"); print n "\t" $0 }' | sort -n -k1,1 -s | cut -f2-
}

# Refuse (before any change) when a manifest file was edited, replaced by a
# symlink or a directory, or is otherwise not what was installed. A missing file
# is fine. Under --force these are allowed, except a non-empty directory.
check_owned_files() {
  local p t why h
  local -a modified=() hard=()
  for p in "${old_file_list[@]}"; do
    t="$target/$p"; why=""
    if [ -L "$t" ]; then why="replaced by a symlink"
    elif [ -d "$t" ]; then why="replaced by a directory"
    elif [ -f "$t" ]; then
      if h="$(hash_of "$t" 2>/dev/null)"; then
        [ "$h" = "${old_files[$p]}" ] || [ "$h" = "${new_hash[$p]:-}" ] || why="modified since install"
      else
        why="unreadable"
      fi
    elif [ -e "$t" ]; then why="not a regular file"
    fi
    [ -n "$why" ] || continue
    if [ "$force" = 1 ]; then
      if [ -d "$t" ] && [ ! -L "$t" ] && [ -n "$(find "$t" -mindepth 1 -print -quit)" ]; then
        hard+=("$p (non-empty directory; --force will not delete it)")
      fi
    else
      modified+=("$p ($why)")
    fi
  done
  if [ ${#hard[@]} -gt 0 ]; then
    echo "install.sh: refusing; nothing was changed:" >&2
    printf '  %s\n' "${hard[@]}" >&2
    exit 1
  fi
  if [ ${#modified[@]} -gt 0 ]; then
    echo "install.sh: refusing; nothing was changed. Installed files differ from what was installed:" >&2
    printf '  %s\n' "${modified[@]}" >&2
    echo "install.sh: this can also follow an interrupted update; re-running install, or --force, resolves it." >&2
    echo "install.sh: --force will overwrite or remove them." >&2
    exit 1
  fi
}

# Remove files, then empty directories (deepest first, never recursive). A
# symlink at a file path is removed as a link, never followed.
remove_entries() { # args: files (array name), dirs (array name)
  local -n _rf="$1" _rd="$2"
  local p i t
  for p in "${_rf[@]}"; do
    t="$target/$p"
    if [ -L "$t" ]; then
      say "remove $p"; [ "$dry_run" = 1 ] || rm -f -- "$t"
    elif [ -d "$t" ]; then
      say "rmdir $p"; [ "$dry_run" = 1 ] || rmdir -- "$t" || die "cannot remove directory $p"
    elif [ -e "$t" ]; then
      say "remove $p"; [ "$dry_run" = 1 ] || rm -f -- "$t"
    fi
  done
  for ((i=${#_rd[@]}-1; i>=0; i--)); do
    p="${_rd[$i]}"
    if [ -d "$target/$p" ] && [ ! -L "$target/$p" ]; then
      say "rmdir $p (if empty)"
      [ "$dry_run" = 1 ] || rmdir -- "$target/$p" 2>/dev/null || true
    fi
  done
}

# --- uninstall ---------------------------------------------------------------

if [ "$mode" = uninstall ]; then
  [ -e "$MANIFEST" ] || die "no manifest at $MANIFEST; nothing to uninstall"
  load_manifest
  check_owned_files
  [ ${#old_dir_list[@]} -eq 0 ] || mapfile -t old_dir_list < <(printf '%s\n' "${old_dir_list[@]}" | sort_dirs_shallow_first)
  remove_entries old_file_list old_dir_list
  say "remove $MANIFEST_NAME"
  [ "$dry_run" = 1 ] || rm -f -- "$MANIFEST"
  exit 0
fi

# --- install: gather and validate the source ---------------------------------

skill_src="$SRC_ROOT/skills/second-brain"
cmd_src="$SRC_ROOT/commands"
[ -d "$skill_src" ] && [ ! -L "$skill_src" ] || die "source skill missing: $skill_src"
[ -d "$cmd_src" ] && [ ! -L "$cmd_src" ] || die "source commands missing: $cmd_src"

new_files=() new_dirs=() src_of=()
declare -A new_file_set=() new_dir_set=()

add_dir() { # $1 = relative dest
  valid_rel D "$1" || die "unsupported directory name in source: ${1//[[:cntrl:]]/?}"
  [ -n "${new_dir_set[$1]+x}" ] || { new_dir_set[$1]=1; new_dirs+=("$1"); }
}
add_file() { # $1 = relative dest, $2 = absolute source
  valid_rel F "$1" || die "unsupported file name in source: ${1//[[:cntrl:]]/?}"
  new_file_set[$1]=1; new_files+=("$1"); src_of+=("$2")
  new_hash[$1]="$(hash_of "$2")" || die "cannot read source file: $2"
}

# Only regular files and directories are allowed; a symlink or special file is
# refused rather than followed.
if [ -n "$(find "$skill_src" "$cmd_src" ! -type f ! -type d -print -quit)" ]; then
  die "source contains symlinks or special files; refusing"
fi

add_dir skills
add_dir skills/second-brain
while IFS= read -r -d '' d; do add_dir "skills/second-brain/${d#"$skill_src"/}"; done \
  < <(find "$skill_src" -mindepth 1 -type d -print0)
while IFS= read -r -d '' f; do add_file "skills/second-brain/${f#"$skill_src"/}" "$f"; done \
  < <(find "$skill_src" -type f -print0)

add_dir commands
cmd_count=0
for f in "$cmd_src"/*.md; do
  [ -f "$f" ] || continue
  add_file "commands/$(basename -- "$f")" "$f"; cmd_count=$((cmd_count+1))
done
[ "$cmd_count" -gt 0 ] || die "no commands/*.md in source"

mapfile -t new_dirs < <(printf '%s\n' "${new_dirs[@]}" | sort_dirs_shallow_first)

load_manifest

# --- preflight: refuse before writing anything -------------------------------

check_owned_files

conflicts=()
for p in "${new_dirs[@]}"; do
  no_symlink_in_path "$p" || { conflicts+=("$p (symlink in path)"); continue; }
  if [ -e "$target/$p" ] && [ ! -d "$target/$p" ] && [ -z "${old_files[$p]+x}" ]; then
    conflicts+=("$p (exists, not a directory)")
  fi
done
for p in "${new_files[@]}"; do
  no_symlink_in_path "$p" parents || { conflicts+=("$p (symlink in path)"); continue; }
  t="$target/$p"
  if [ -e "$t" ] || [ -L "$t" ]; then
    if [ -n "${old_files[$p]+x}" ]; then :   # ours; state was checked above
    elif [ -n "${old_dirs[$p]+x}" ] && [ -d "$t" ] && [ ! -L "$t" ]; then
      # a directory we created is becoming a file: only our own leftovers may be inside
      while IFS= read -r -d '' q; do
        q="${q#"$target"/}"
        [ -n "${old_files[$q]+x}" ] || [ -n "${old_dirs[$q]+x}" ] || conflicts+=("$q (inside $p, not installed by this script)")
      done < <(find "$t" -mindepth 1 -print0)
    else
      conflicts+=("$p (exists and was not installed by this script)")
    fi
  fi
done
if [ ${#conflicts[@]} -gt 0 ]; then
  echo "install.sh: refusing to install; nothing was changed. Conflicts:" >&2
  printf '  %s\n' "${conflicts[@]}" >&2
  exit 1
fi

# Directories this script owns afterwards: previously recorded ones plus any it creates now.
owned_dirs=()
for p in "${new_dirs[@]}"; do
  if [ -n "${old_dirs[$p]+x}" ] || [ -n "${old_files[$p]+x}" ] || [ ! -e "$target/$p" ]; then
    owned_dirs+=("$p")
  fi
done

stale_files=() stale_dirs=()
for p in "${old_file_list[@]}"; do [ -n "${new_file_set[$p]+x}" ] || stale_files+=("$p"); done
for p in "${old_dir_list[@]}"; do [ -n "${new_dir_set[$p]+x}" ] || stale_dirs+=("$p"); done
[ ${#stale_dirs[@]} -eq 0 ] || mapfile -t stale_dirs < <(printf '%s\n' "${stale_dirs[@]}" | sort_dirs_shallow_first)

# --- install -----------------------------------------------------------------

if [ "$dry_run" = 1 ]; then
  remove_entries stale_files stale_dirs
  for p in "${owned_dirs[@]}"; do [ -d "$target/$p" ] || say "mkdir $p"; done
  for p in "${new_files[@]}"; do
    if [ -e "$target/$p" ] || [ -L "$target/$p" ]; then say "update $p"; else say "install $p"; fi
  done
  exit 0
fi

mkdir -p -- "$target"

# Write the manifest first, listing old and new entries, so an interrupted run
# leaves everything it may have created recorded (uninstall tolerates missing
# files). An existing file keeps its old hash until it is replaced; the check
# above also accepts the new content's hash, so a half-updated tree is not
# mistaken for user edits.
declare -A pre_hash=()
union_files=("${new_files[@]}")
for p in "${new_files[@]}"; do
  if [ -n "${old_files[$p]+x}" ]; then pre_hash[$p]="${old_files[$p]}"; else pre_hash[$p]="${new_hash[$p]}"; fi
done
for p in "${stale_files[@]}"; do union_files+=("$p"); pre_hash[$p]="${old_files[$p]}"; done
union_dirs=("${owned_dirs[@]}")
for p in "${stale_dirs[@]}"; do union_dirs+=("$p"); done
write_manifest union_files union_dirs pre_hash

# Clear what a previous version installed that the source no longer has (this
# also clears an old file or directory sitting where the other type is needed).
remove_entries stale_files stale_dirs

for p in "${new_dirs[@]}"; do
  [ -d "$target/$p" ] && [ ! -L "$target/$p" ] || { say "mkdir $p"; mkdir -- "$target/$p"; }
done
for i in "${!new_files[@]}"; do
  p="${new_files[$i]}"; t="$target/$p"
  tmp="$(mktemp "$target/$(dirname -- "$p")/.sbw-tmp.XXXXXX")"
  TMPFILES+=("$tmp")
  cp -- "${src_of[$i]}" "$tmp"
  chmod 644 "$tmp"
  if [ -e "$t" ] || [ -L "$t" ]; then
    say "update $p"
    # a directory here is an empty one accepted under --force; mv -fT replaces a symlink itself
    if [ -d "$t" ] && [ ! -L "$t" ]; then rmdir -- "$t"; fi
  else
    say "install $p"
  fi
  mv -fT -- "$tmp" "$t"
done

write_manifest new_files owned_dirs new_hash
say "installed ${#new_files[@]} files into $target"

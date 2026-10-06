#!/bin/sh
set -e
# Reinstall when the node_modules volume is empty or package-lock.json is newer
# than the install marker npm writes.
if [ ! -f node_modules/.package-lock.json ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
  npm ci
fi
exec "$@"

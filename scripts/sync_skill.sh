#!/usr/bin/env bash
# Keep skills/autonomous-research identical to the canonical bundle in getedgehq/skills (main).
#   scripts/sync_skill.sh          replace the local folder with upstream
#   scripts/sync_skill.sh --check  exit 1 if any file differs (SHA-256 manifest)
set -euo pipefail

UPSTREAM="${SKILL_UPSTREAM:-https://github.com/getedgehq/skills}"
REF="${SKILL_REF:-main}"
NAME="autonomous-research"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/skills/$NAME"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

git clone -q --depth 1 --branch "$REF" --filter=blob:none --sparse "$UPSTREAM" "$TMP/up"
git -C "$TMP/up" sparse-checkout set "$NAME"
SRC="$TMP/up/$NAME"
[ -f "$SRC/SKILL.md" ] || { echo "upstream $NAME/SKILL.md not found" >&2; exit 2; }
REV="$(git -C "$TMP/up" rev-parse --short HEAD)"

manifest() { (cd "$1" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum); }

if [ "${1:-}" = "--check" ]; then
  if diff <(manifest "$SRC") <(manifest "$DEST"); then
    echo "skills/$NAME matches $UPSTREAM@$REF ($REV)"
  else
    echo "skills/$NAME differs from $UPSTREAM@$REF ($REV); run scripts/sync_skill.sh" >&2
    exit 1
  fi
else
  rm -rf "$DEST"
  mkdir -p "$(dirname "$DEST")"
  cp -R "$SRC" "$DEST"
  echo "synced skills/$NAME from $UPSTREAM@$REF ($REV)"
fi

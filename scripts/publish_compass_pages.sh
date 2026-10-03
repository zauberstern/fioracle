#!/usr/bin/env bash
# Build static Bubble Compass into docs/compass for GitHub Pages.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY=python3
fi
"$PY" scripts/export_compass_pages.py

BODY="$ROOT/bubble_compass/body"
GAME="$ROOT/bubble_compass/game"
DEST="$ROOT/docs/compass"

mkdir -p "$DEST/desk"

(
  cd "$BODY"
  PAGES_BASE=/fioracle/compass/ npm run build
)
rsync -a --delete \
  --exclude data \
  --exclude desk \
  "$BODY/dist/" "$DEST/"

(
  cd "$GAME"
  PAGES_BASE=/fioracle/compass/desk/ \
    VITE_HISTORY_BASE=/fioracle/compass/data/ \
    npm run build
)
rsync -a --delete "$GAME/dist/" "$DEST/desk/"

# Keep exported tape (export runs first; rsync --exclude data preserves it)
test -f "$DEST/data/manifest.json"
test -f "$DEST/index.html"
test -f "$DEST/desk/index.html"
echo "published $DEST"

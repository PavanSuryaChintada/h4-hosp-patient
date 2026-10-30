#!/usr/bin/env sh
# One-click demo on macOS / Linux: build the web app, start the ward server on an empty ward and
# open the sign-in page. Previous ward records are moved to data/ward/archive/, not deleted.
# Add --keep to carry on with the ward as it was:  ./demo.sh --keep
cd "$(dirname "$0")" || exit 1

PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python

if command -v npm >/dev/null 2>&1; then
  (cd ui && { [ -d node_modules ] || npm ci; } && npm run build)
else
  echo "npm not found: serving the last build in ui/dist"
fi

if [ "$1" = "--keep" ]; then
  exec "$PY" tools/serve_ui.py --open
else
  exec "$PY" tools/serve_ui.py --fresh --open
fi

#!/usr/bin/env bash
# Build the read-only public site from the lab database: scripts/build_public.sh <out_dir>
set -euo pipefail
OUT=$(realpath -m "${1:?usage: build_public.sh <out_dir>}")
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PY=${PYTHON:-python}
rm -rf "$ROOT/web/public/data"
(cd "$ROOT/backend" && "$PY" -m lineage.cli export ../web/public/data)
(cd "$ROOT/web" && VITE_STATIC=1 VITE_BASE="${VITE_BASE:-/lineage/}" npx vite build --outDir "$OUT" --emptyOutDir)
rm -rf "$ROOT/web/public/data"

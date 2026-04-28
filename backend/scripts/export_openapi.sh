#!/usr/bin/env bash
# Fetch OpenAPI JSON from a running Leaderboard API (default http://127.0.0.1:5001).
# Usage: OPENAPI_BASE_URL=http://localhost:5001 ./scripts/export_openapi.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$BACKEND_ROOT/.." && pwd)"
OUT="${OPENAPI_OUT:-${REPO_ROOT}/artifacts/openapi.json}"
mkdir -p "$(dirname "$OUT")"
BASE="${OPENAPI_BASE_URL:-http://127.0.0.1:5001}"
curl -sSf "${BASE%/}/openapi.json" -o "$OUT"
echo "Wrote ${OUT}"

#!/usr/bin/env bash
# Fetch GET /public/submission_format for a dataset; response includes a ready-made submit_model_body.
# Usage: LEADERBOARD_API=http://127.0.0.1:5001 ./scripts/submit_model_example.sh "My Dataset Name"
set -euo pipefail
BASE="${LEADERBOARD_API:-http://127.0.0.1:5001}"
DATASET="${1:-flores_spanish_translation}"
ENC="$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$DATASET")"

curl -sS "${BASE}/public/submission_format?dataset=${ENC}" | python3 -m json.tool
echo
echo "POST the submit_model_body object to: ${BASE}/public/submit_model (add API key header if configured)."

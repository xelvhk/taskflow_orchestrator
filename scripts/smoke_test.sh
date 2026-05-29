#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "Checking API readiness at ${BASE_URL}..."
curl --fail --silent "${BASE_URL}/ready" >/dev/null

echo "Creating demo API key..."
API_KEY="$(docker compose exec -T api python -m app.cli create-api-key --name smoke | tail -n 1)"

echo "Creating summarize_text task..."
CREATE_RESPONSE="$(
  curl --fail --silent -X POST "${BASE_URL}/tasks" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${API_KEY}" \
    -H "Idempotency-Key: smoke-$(date +%s)" \
    -d '{"type":"summarize_text","payload":{"text":"Smoke tests prove the API, database, broker, and worker can complete one background job."},"max_retries":2}'
)"

TASK_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"${CREATE_RESPONSE}")"
echo "Created task ${TASK_ID}; waiting for worker result..."

for _ in $(seq 1 30); do
  TASK_RESPONSE="$(curl --fail --silent "${BASE_URL}/tasks/${TASK_ID}" -H "X-API-Key: ${API_KEY}")"
  STATUS="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"${TASK_RESPONSE}")"

  if [[ "${STATUS}" == "succeeded" ]]; then
    echo "Smoke test passed."
    echo "${TASK_RESPONSE}"
    exit 0
  fi

  if [[ "${STATUS}" == "failed" || "${STATUS}" == "dead_letter" || "${STATUS}" == "cancelled" ]]; then
    echo "Smoke test failed with terminal status: ${STATUS}" >&2
    echo "${TASK_RESPONSE}" >&2
    exit 1
  fi

  sleep 1
done

echo "Smoke test timed out waiting for task ${TASK_ID}." >&2
exit 1

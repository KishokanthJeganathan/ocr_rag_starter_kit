#!/usr/bin/env bash
# Upload a fixture PDF and show the OCR layout the worker produced.
#   bash scripts/try-ocr.sh [path/to.pdf]
set -euo pipefail

FIXTURE="${1:-fixtures/nda_02000.pdf}"
API="${API:-http://localhost:8000}"
TENANT="00000000-0000-0000-0000-000000000001"
MATTER="00000000-0000-0000-0000-000000000002"

command -v jq >/dev/null 2>&1 && PP="jq ." || PP="python3 -m json.tool"

echo "-> seeding demo tenant/matter"
docker compose run --rm api python -m scripts.seed >/dev/null

echo "-> uploading $FIXTURE"
RESP=$(curl -sS -F "file=@${FIXTURE}" -F "matter_id=${MATTER}" \
  -H "X-Tenant-Id: ${TENANT}" "${API}/v1/documents")

if ! echo "$RESP" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
  echo "!! upload failed. raw response:"
  echo "${RESP:-<empty>}"
  echo "--- api log (last 25) ---"
  docker compose logs api --tail 25
  exit 1
fi
echo "$RESP" | $PP

DOC=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['document']['id'])")
echo "-> document id: $DOC"

echo "-> waiting for the worker (OCR -> classify -> extract)..."
for _ in $(seq 1 40); do
  STATUS=$(curl -sS -H "X-Tenant-Id: ${TENANT}" "${API}/v1/documents/${DOC}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "   status=$STATUS"
  [ "$STATUS" = "processed" ] && break
  [ "$STATUS" = "failed" ] && break
  sleep 2
done

echo
echo "=== document ==="
curl -sS -H "X-Tenant-Id: ${TENANT}" "${API}/v1/documents/${DOC}" | $PP

echo
echo "=== layout ==="
curl -sS -H "X-Tenant-Id: ${TENANT}" "${API}/v1/documents/${DOC}/layout" | $PP || true

echo
echo "=== extraction ==="
curl -sS -H "X-Tenant-Id: ${TENANT}" "${API}/v1/documents/${DOC}/extraction" | $PP || true

echo
echo "=== worker log (last 15) ==="
docker compose logs worker --tail 15

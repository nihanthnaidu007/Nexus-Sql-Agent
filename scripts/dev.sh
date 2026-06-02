#!/usr/bin/env bash
# Launch DB (docker), API (uvicorn), and UI (streamlit) on auto-picked free ports.
# Override any of: DB_HOST_PORT, API_PORT, UI_PORT
set -euo pipefail

cd "$(dirname "$0")/.."

free_port() {
  python3 -c 'import socket; s=socket.socket(); s.bind(("",0)); print(s.getsockname()[1]); s.close()'
}

DB_HOST_PORT="${DB_HOST_PORT:-$(free_port)}"
API_PORT="${API_PORT:-$(free_port)}"
UI_PORT="${UI_PORT:-$(free_port)}"

export DB_HOST_PORT API_PORT UI_PORT
export DATABASE_URL="postgresql://nixus:nixus@localhost:${DB_HOST_PORT}/nixus_sql"
export API_BASE_URL="http://localhost:${API_PORT}"

cat <<EOF
─────────────────────────────────────────
  NIXUS SQL — dev runner
─────────────────────────────────────────
  DB   → localhost:${DB_HOST_PORT}
  API  → ${API_BASE_URL}
  UI   → http://localhost:${UI_PORT}
─────────────────────────────────────────
EOF

echo "◈ Starting database container..."
docker compose up -d db >/dev/null

echo "◈ Waiting for database to become healthy..."
for i in $(seq 1 30); do
  status="$(docker inspect -f '{{.State.Health.Status}}' nixus-sql-agent-db-1 2>/dev/null || echo starting)"
  if [ "$status" = "healthy" ]; then
    echo "  ✓ database ready"
    break
  fi
  sleep 2
  if [ "$i" = "30" ]; then
    echo "✗ database failed to become healthy"
    exit 1
  fi
done

cleanup() {
  echo ""
  echo "◈ Shutting down API + UI..."
  jobs -p | xargs -r kill 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "◈ Launching FastAPI on :${API_PORT}..."
uvicorn api.main:app --host 127.0.0.1 --port "$API_PORT" --reload &

echo "◈ Launching Streamlit on :${UI_PORT}..."
streamlit run ui/app.py \
  --server.port "$UI_PORT" \
  --server.headless true \
  --browser.gatherUsageStats false &

wait

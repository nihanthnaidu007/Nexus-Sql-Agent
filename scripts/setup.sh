#!/usr/bin/env bash
# ============================================================================
# 7.2 — One script, clone to running. Idempotent and safe to re-run.
#
# What it does:
#   1. Check prerequisites (Docker + `docker compose`); report clearly if missing.
#   2. Create .env from .env.example (if absent) and prompt for the two required
#      API keys — WITHOUT echoing them and WITHOUT committing them.
#   3. Bring up the self-contained SaaS stack: `docker compose up -d --build`.
#   4. Wait for health, then print the next step.
#
# It NEVER prints secrets, NEVER `git add`s .env, and NEVER deletes volumes
# (no `down -v`). The only required input is the two API keys.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf '\033[36m◈ %s\033[0m\n' "$*"; }
err() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; }

# ── 1. prerequisites ────────────────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  err "Docker with the 'docker compose' plugin is required and was not found."
  echo "  Install Docker Desktop: https://docs.docker.com/get-docker/  then re-run."
  echo "  (Or use the local dev path: python -m venv .venv &&"
  echo "   .venv/bin/pip install -r requirements.txt && ./start.sh)"
  exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
  err "curl is required for the health check."; exit 1
fi

# ── 2. .env + required keys (no echo, no commit) ────────────────────────────
if [ -f .env ]; then
  say ".env already exists — leaving it untouched (your keys are safe)."
else
  cp .env.example .env
  say "Created .env from .env.example (gitignored — never committed)."
fi

# Prompt for a key only if it is still a placeholder/empty; write it without echo.
prompt_key() {
  local var="$1" label="$2" cur val
  cur="$(grep -E "^${var}=" .env | head -1 | cut -d= -f2- || true)"
  case "$cur" in
    ""|your_*)
      printf 'Enter %s (input hidden, not echoed): ' "$label"
      read -rs val; echo
      if [ -z "$val" ]; then err "$var is required."; exit 1; fi
      # Pass via env (not argv) so the secret never appears in `ps`.
      KEY_NAME="$var" KEY_VALUE="$val" python - <<'PYEOF'
import os, pathlib, re
var, val = os.environ["KEY_NAME"], os.environ["KEY_VALUE"]
p = pathlib.Path(".env"); lines = p.read_text().splitlines()
pat = re.compile(rf"^{var}="); out, seen = [], False
for ln in lines:
    if pat.match(ln):
        out.append(f"{var}={val}"); seen = True
    else:
        out.append(ln)
if not seen:
    out.append(f"{var}={val}")
p.write_text("\n".join(out) + "\n")
PYEOF
      unset val
      say "$var set."
      ;;
    *)
      say "$var already set — keeping it."
      ;;
  esac
}
prompt_key OPENAI_API_KEY "OpenAI API key  (schema embeddings)"
prompt_key ANTHROPIC_API_KEY "Anthropic API key  (the agent LLM)"

# ── 3. bring the stack up (default: self-contained SaaS demo) ────────────────
say "Building + starting the stack (docker compose up -d --build)..."
docker compose up -d --build

# ── 4. wait for health, print next step ─────────────────────────────────────
say "Waiting for the API (first boot runs migrations + embeds the SaaS schema)..."
for i in $(seq 1 60); do
  if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
    say "API healthy."
    cat <<'EOF'

─────────────────────────────────────────
  NIXUS is running — self-contained SaaS sample (read-only target).
  Try it:
    open http://localhost:8000/docs        # API + Swagger
    open http://localhost:8501             # Streamlit UI
    nixus query "how many organizations are there?"
─────────────────────────────────────────
EOF
    exit 0
  fi
  sleep 3
done
err "API did not become healthy in time. Inspect logs: docker compose logs api"
exit 1

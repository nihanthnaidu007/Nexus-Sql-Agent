#!/usr/bin/env bash
# ============================================================================
# 7.2 — ONE operation to point the WHOLE stack at a single target, coherently.
#
# Replaces the old three-setting juggling (TARGET_DATABASE_URL +
# TARGET_ADMIN_DATABASE_URL + a manual reembed, easy to get out of sync). This
# sets both target URLs in .env AND re-embeds, so the API, the embeddings, and
# the benchmark are always aligned to the SAME target.
#
#   scripts/use_target.sh saas        # the bundled SaaS sample (default)
#   scripts/use_target.sh chinook     # the alt Chinook sample
#   scripts/use_target.sh postgresql://readonly_user:pw@host:5432/yourdb   # BYO
#
# After it runs, RESTART the API so it serves the new target (the running process
# captured the old env at startup):
#   local : stop the API and re-run it (uvicorn / ./start.sh / scripts/dev.sh)
#   docker: docker compose restart api
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

NAME="${1:-}"
if [ -z "$NAME" ]; then
  echo "usage: scripts/use_target.sh <saas|chinook|postgresql://readonly-url>"
  exit 2
fi
if [ ! -f .env ]; then
  echo "✗ No .env found. Run scripts/setup.sh (or cp .env.example .env) first."
  exit 1
fi

# host:port for the local sample DBs comes from the current TARGET line (default 5433).
HOSTPORT="$(grep -E '^TARGET_DATABASE_URL=' .env | head -1 | sed -E 's#.*@([^/]+)/.*#\1#')"
[ -n "$HOSTPORT" ] || HOSTPORT="localhost:5433"

case "$NAME" in
  saas)
    RO="postgresql://nixus_readonly:nixus_readonly@${HOSTPORT}/nixus_saas"
    ADMIN="postgresql://nixus:nixus@${HOSTPORT}/nixus_saas" ;;
  chinook)
    RO="postgresql://nixus_readonly:nixus_readonly@${HOSTPORT}/nixus_chinook"
    ADMIN="postgresql://nixus:nixus@${HOSTPORT}/nixus_chinook" ;;
  postgresql://*|postgres://*)
    RO="$NAME"; ADMIN="" ;;   # bring-your-own read-only target: no owner, no rebuild
  *)
    echo "✗ Unknown target '$NAME' (expected: saas | chinook | a postgresql:// URL)"
    exit 2 ;;
esac

# Rewrite the two TARGET lines in .env so API + benchmark align to one target.
RO="$RO" ADMIN="$ADMIN" python - <<'PYEOF'
import os, pathlib, re
ro, admin = os.environ["RO"], os.environ["ADMIN"]
p = pathlib.Path(".env"); lines = p.read_text().splitlines()
def setline(lines, key, val):
    pat = re.compile(rf"^{key}="); out, seen = [], False
    for ln in lines:
        if pat.match(ln):
            out.append(f"{key}={val}"); seen = True
        else:
            out.append(ln)
    if not seen:
        out.append(f"{key}={val}")
    return out
lines = setline(lines, "TARGET_DATABASE_URL", ro)
if admin:
    lines = setline(lines, "TARGET_ADMIN_DATABASE_URL", admin)
p.write_text("\n".join(lines) + "\n")
print(f"  ✓ .env TARGET_DATABASE_URL -> {ro}")
PYEOF

echo "◈ Re-embedding schema_embeddings from the new target (introspection)..."
TARGET_DATABASE_URL="$RO" TARGET_ADMIN_DATABASE_URL="${ADMIN:-$RO}" \
  .venv/bin/python -m nixus.schema.reembed

cat <<EOF
◈ Target switched to: $NAME
  - .env updated (the API + eval/run_saas_benchmark.py now read this target)
  - schema_embeddings re-embedded for it
  RESTART the API to serve it:
    local : re-run the API (uvicorn / ./start.sh / scripts/dev.sh)
    docker: docker compose restart api
EOF

# NIXUS — Setup (quickstart stub)

> Brief setup notes for Phase 7.2. The full README lands in 7.3; this is the
> minimum to get a stranger from a clean clone to a working query.

## Default: the self-contained SaaS demo (clone → one command → querying)

The default stack is **self-contained**: it ships a bundled B2B-SaaS sample
database, provisions it read-only, embeds it, and serves it — with **no
connection string and no external database**. The only thing you supply is two
API keys (an OpenAI key for schema embeddings, an Anthropic key for the agent).

```bash
# guided (recommended): creates .env, prompts for the keys (no echo), brings it up
scripts/setup.sh

# …or manually:
[ -f .env ] || cp .env.example .env   # only if you don't already have a .env; then
                                      # set OPENAI_API_KEY + ANTHROPIC_API_KEY in .env
docker compose up -d --build
```

On first boot the app, in order: waits for Postgres → runs migrations → ensures
the SaaS sample is loaded + seeded → embeds the SaaS schema → starts the API. If
a key is missing it **fails fast** with a clear message instead of booting broken.

Then, from a clean state, these work with no other steps:

```bash
curl -s http://localhost:8000/api/health                  # healthy, db_connected: true
nixus query "how many organizations are there?"           # answers against SaaS
nixus query "which organization has the most users?"      # a real result
```

### Clean bring-up (the only honest test — destroys local data, so it's your call)

```bash
docker compose down -v                 # wipe volumes — your deliberate action
[ -f .env ] || cp .env.example .env    # only if you have no .env; then set the two keys
docker compose up -d --build           # provisions, seeds, embeds, boots — automatically
```

## Switching the target — one operation

Point the **whole** stack (API + embeddings + benchmark) at a target with a
single command; it updates both target URLs in `.env` and re-embeds, then asks
you to restart the API:

```bash
scripts/use_target.sh saas       # the bundled SaaS sample (default)
scripts/use_target.sh chinook    # the alt Chinook sample
# docker: docker compose restart api   |   local: re-run the API
```

## Step two — bring your own database (real use)

For real use, point NIXUS at **your own** Postgres through a role that holds
**only `SELECT`** (ideally a read replica). NIXUS needs nothing more than SELECT
on the target — read-only is enforced by Postgres, not by the app choosing not to
write.

```bash
scripts/use_target.sh postgresql://readonly_user:pw@your-host:5432/yourdb
# then restart the API and query your real data.
```

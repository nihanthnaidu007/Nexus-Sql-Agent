-- ============================================================================
-- Phase 15 — RICH DEMO seed for the SaaS sample (the LIVE-DEMO/UI data).
--
-- THIS IS NOT THE BENCHMARK. The benchmark of record runs against the FROZEN
-- eval/saas_seed.sql in the `nixus_saas` database with a gold set tied to that
-- exact data. This file is a SEPARATE, deliberately RICH seed loaded into a
-- SEPARATE database (`nixus_saas_demo`) by scripts/rebuild_demo_db.py. Because
-- the two live in different databases, this demo data can NEVER contaminate the
-- benchmark — separation makes it structurally impossible. Do NOT wire this seed
-- into the benchmark, and do NOT regenerate the gold set against it.
--
-- SAME SCHEMA as eval/saas_schema.sql (same tables, same columns, same enums) —
-- this seed adds only MORE, time-spread data so the UI's wide charts have rich
-- material to draw:
--   * ~40 organizations with realistic name variation (a rich "users per org"
--     bar chart with many bars and clear variation).
--   * ~600 users spread NON-UNIFORMLY across orgs (some large, some small).
--   * 8 plans across all three tiers; subscriptions SKEWED toward lower tiers
--     (a realistic "subscriptions by plan" bar chart, not a flat one).
--   * usage_events / invoices / payments dated ACROSS ~18 MONTHS (2024-01 ..
--     2025-06) with a GENTLE UPWARD GROWTH trend, so the time-series questions
--     ("revenue by month", "new signups per month", "usage events per month")
--     each produce a real multi-bucket LINE chart that trends up.
--
-- DETERMINISM (so the demo is stable + reproducible — verify with --verify):
--   This file uses NO randomness and NO now()/CURRENT_* — ONLY fixed literals
--   and pure arithmetic over generate_series. Every INSERT ... SELECT carries an
--   ORDER BY, so the GENERATED-IDENTITY surrogate keys (users, usage_events,
--   invoices, payments) are assigned in a fixed order and are reproducible. Two
--   rebuilds produce byte-identical rows — exactly the guarantee saas_seed.sql
--   makes for the benchmark, applied here to the demo.
--
-- VOLUME is tuned to be rich but SNAPPY: ~600 users, ~4.3k usage_events, ~600
-- invoices, ~520 payments — aggregations stay sub-second.
-- ============================================================================

-- ── plans: 8 across all three tiers (free / pro / enterprise) ───────────────
-- More tiers than the benchmark's 5 so "subscriptions by plan" has more bars.
INSERT INTO plans (id, name, tier, monthly_price, seat_limit) VALUES
  (1, 'Free',            'free',          0.00,    3),
  (2, 'Starter',         'pro',          29.00,    5),
  (3, 'Pro Monthly',     'pro',          79.00,   15),
  (4, 'Pro Annual',      'pro',         790.00,   15),
  (5, 'Team',            'pro',         149.00,   25),
  (6, 'Business',        'enterprise',  399.00,   50),
  (7, 'Enterprise',      'enterprise',  999.00,  200),
  (8, 'Enterprise Plus', 'enterprise', 2499.00, 1000);

-- ── organizations: 40, created across ~17 months for "new orgs per month" ───
-- plan_id is drawn from a WEIGHTED array (lower tiers more common) so the plan
-- mix is realistically skewed. created_at marches forward 13 days per org from
-- 2024-01-04 (org 1) to ~2025-06 (org 40). ~1 in 11 is inactive.
INSERT INTO organizations (id, name, plan_id, created_at, country, is_active)
SELECT gs,
       (ARRAY[
         'Acme Corp','Globex','Initech','Umbrella Labs','Hooli','Stark Industries',
         'Wayne Enterprises','Wonka Foods','Cyberdyne','Soylent','Tyrell','Vandelay',
         'Pied Piper','Aviato','Nakatomi','Massive Dynamic','Vehement Capital',
         'Gekko & Co','Bluth Company','Dunder Mifflin','Prestige Worldwide',
         'Hanso Foundation','Oscorp','LexCorp','Wernham Hogg','Sterling Cooper',
         'Los Pollos','Cogswell Cogs','Spacely Sprockets','Monsters Inc',
         'Sirius Cybernetics','Tessier-Ashpool','Weyland-Yutani','Encom',
         'Cheyenne Mountain','Abstergo','Black Mesa','Aperture Labs',
         'Strickland Propane','Vault-Tec'
       ])[gs],
       (ARRAY[1,1,1,1,2,2,2,3,3,3,4,4,5,6,7,8])[1 + (gs % 16)],   -- weighted plan mix
       TIMESTAMP '2024-01-04 09:00:00'
         + ((gs - 1) * 13) * INTERVAL '1 day'
         + (gs % 8) * INTERVAL '1 hour',
       (ARRAY['US','GB','DE','CA','FR','JP','AU','IN','BR','NL'])[1 + (gs % 10)],
       (gs % 11 <> 0)
FROM generate_series(1, 40) AS gs
ORDER BY gs;

-- ── users: NON-UNIFORM per-org counts -> a rich, varied bar chart ───────────
-- count per org = 8 + ((id*13 + 7) % 35)  => 8..42 users, varied across orgs
-- (minimum 8/org * 40 orgs => >= 320 users, so any users.id in 1..250 is valid
-- to reference below). created_at is staggered AFTER the org's creation so
-- aggregate "new signups per month" spreads across the whole window and grows.
-- role cycles admin/member/viewer; last_active_at is NULL for every 4th user.
INSERT INTO users (organization_id, email, full_name, role, created_at, last_active_at)
SELECT o.id,
       'user' || u || '.org' || o.id || '@example.com',
       (ARRAY['Alex','Sam','Jordan','Taylor','Morgan','Casey','Riley','Jamie',
              'Avery','Quinn','Drew','Robin'])[1 + ((u * 3 + o.id) % 12)]
         || ' ' ||
       (ARRAY['Smith','Johnson','Lee','Brown','Garcia','Martin','Davis','Clark',
              'Lewis','Walker','Young','Hall'])[1 + ((u * 5 + o.id) % 12)],
       (ARRAY['admin','member','viewer'])[1 + ((u - 1) % 3)]::user_role,
       o.created_at + (u * 4 + (o.id % 9)) * INTERVAL '1 day',
       CASE WHEN u % 4 = 0 THEN NULL
            ELSE o.created_at + (u * 4 + 30 + (o.id % 40)) * INTERVAL '1 day'
       END
FROM (SELECT id, created_at, (8 + ((id * 13 + 7) % 35)) AS cnt FROM organizations) o
CROSS JOIN LATERAL generate_series(1, o.cnt) AS u
ORDER BY o.id, u;

-- ── subscriptions: one per org, plan = the org's plan (so "subscriptions by ──
-- plan" mirrors the skewed plan mix). Statuses cycle active/trialing/past_due/
-- canceled; canceled_at is set only on the canceled rows.
INSERT INTO subscriptions (id, organization_id, plan_id, status, started_at, canceled_at, seats)
SELECT o.id, o.id, o.plan_id,
       (ARRAY['active','active','active','trialing','past_due','canceled'])[1 + (o.id % 6)]::subscription_status,
       o.created_at,
       CASE WHEN (o.id % 6) = 5
            THEN o.created_at + 200 * INTERVAL '1 day'
            ELSE NULL
       END,
       5 + (o.id % 50)
FROM organizations o
ORDER BY o.id;

-- ── usage_events: ~4.3k across 540 days (2024-01-01 .. ~2025-06) ────────────
-- events-per-day GROWS (2 + d/45 => 2..13) so "usage events per month" trends
-- UP across ~18 buckets. occurred_at uses date arithmetic only (deterministic).
-- user_id is NULL for every 5th event (the nullable FK); otherwise a valid
-- users.id in 1..250 (safe: >= 320 users exist). quantity varies 1..12.
INSERT INTO usage_events (organization_id, user_id, event_type, occurred_at, quantity)
SELECT 1 + ((d * 7 + e) % 40),                                      -- orgs 1..40
       CASE WHEN e % 5 = 0 THEN NULL
            ELSE 1 + ((d * 3 + e) % 250) END,                       -- valid users.id
       (ARRAY['login','api_call','export','report_view','webhook'])[1 + ((d + e) % 5)],
       TIMESTAMP '2024-01-01 00:00:00'
         + d * INTERVAL '1 day'
         + (e % 24) * INTERVAL '1 hour',
       1 + (e % 12)
FROM generate_series(0, 539) AS d
CROSS JOIN LATERAL generate_series(1, 2 + (d / 45)) AS e
ORDER BY d, e;

-- ── invoices: ~600 across 18 MONTHLY buckets (2024-01 .. 2025-06), growing ──
-- invoices-per-month = 25 + m (month 0 => 25 .. month 17 => 42). issued_at steps
-- by whole months so date_trunc('month', ...) yields clean 18 buckets. Most are
-- 'paid' (=> a payment); a few 'open'/'void'. amount varies 50.00 .. 525.00.
INSERT INTO invoices (organization_id, amount, status, issued_at, due_at)
SELECT 1 + ((m * 7 + k) % 40),                                      -- orgs 1..40
       (50 + ((m * 5 + k * 3) % 20) * 25)::numeric(10, 2),          -- 50..525
       (CASE WHEN k % 8 = 0  THEN 'open'
             WHEN k % 13 = 0 THEN 'void'
             ELSE 'paid' END)::invoice_status,
       TIMESTAMP '2024-01-10 00:00:00'
         + m * INTERVAL '1 month'
         + (k % 26) * INTERVAL '1 day',
       TIMESTAMP '2024-01-10 00:00:00'
         + m * INTERVAL '1 month'
         + ((k % 26) + 15) * INTERVAL '1 day'
FROM generate_series(0, 17) AS m
CROSS JOIN LATERAL generate_series(1, 25 + m) AS k
ORDER BY m, k;

-- ── payments: one per PAID invoice (~520) -> "revenue by month" tracks the ──
-- invoice buckets and trends up. paid_at is a few days after issue (same month),
-- amount equals the invoice amount. method varies across 4 channels.
INSERT INTO payments (invoice_id, amount, paid_at, method)
SELECT i.id,
       i.amount,
       i.issued_at + ((i.id % 5) + 1) * INTERVAL '1 day',
       (ARRAY['card','bank_transfer','paypal','wire'])[1 + (i.id % 4)]
FROM invoices i
WHERE i.status = 'paid'
ORDER BY i.id;
-- (Table/column COMMENTs live in eval/saas_schema.sql — the demo reuses that
--  schema unchanged, so they are already applied; the seed only adds data.)

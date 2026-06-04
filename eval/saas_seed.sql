-- ============================================================================
-- 6.1 — DETERMINISTIC, KNOWN seed for the SaaS sample database.
--
-- THE GOVERNING RULE: this seed is deterministic and known. The 6.2 gold answers
-- are computed by running gold SQL against THIS exact data, so every value must
-- be stable across rebuilds. This file uses NO randomness and NO now()/CURRENT_*
-- — only fixed literals and pure arithmetic over generate_series — so every
-- rebuild produces byte-identical rows. Identity ids are assigned in a fixed
-- order (every INSERT ... SELECT carries an ORDER BY), so even the surrogate
-- keys are reproducible.
--
-- KNOWN, DETERMINATE answers baked in (verified by querying after load):
--   * most users:        organization 1 (Acme Corp) with 12 users — unique, no tie.
--   * paid revenue:      SUM(paid invoices) = 9750.00 (= SUM(payments)).
--   * canceled subs:     exactly 3 (subscription ids 11, 12, 13).
--   * zero-usage orgs:   organizations 11 and 12 have no usage_events (LEFT join).
--   * monthly structure: usage_events span Jan–Oct 2024 (one per day), invoices
--                        Jan–Oct 2024 — real buckets for time-series queries.
-- ============================================================================

-- ── plans: 5 (one per tier + a pro and an enterprise variant) ───────────────
INSERT INTO plans (id, name, tier, monthly_price, seat_limit) VALUES
  (1, 'Free',            'free',         0.00,   3),
  (2, 'Pro Monthly',     'pro',         49.00,  10),
  (3, 'Pro Annual',      'pro',        490.00,  10),
  (4, 'Enterprise',      'enterprise', 499.00, 100),
  (5, 'Enterprise Plus', 'enterprise', 999.00, 500);

-- ── organizations: 12 across plans and countries; 2 inactive (10, 11) ───────
INSERT INTO organizations (id, name, plan_id, created_at, country, is_active) VALUES
  (1,  'Acme Corp',         4, '2023-01-10 09:00:00', 'US', true),
  (2,  'Globex',            2, '2023-02-15 10:30:00', 'US', true),
  (3,  'Initech',           2, '2023-03-20 11:00:00', 'GB', true),
  (4,  'Umbrella',          5, '2023-04-05 14:00:00', 'DE', true),
  (5,  'Hooli',             3, '2023-05-12 08:45:00', 'US', true),
  (6,  'Stark Industries',  4, '2023-06-18 16:20:00', 'US', true),
  (7,  'Wayne Enterprises', 3, '2023-07-22 13:10:00', 'CA', true),
  (8,  'Wonka',             1, '2023-08-30 09:30:00', 'GB', true),
  (9,  'Cyberdyne',         2, '2023-09-14 12:00:00', 'FR', true),
  (10, 'Soylent',           1, '2023-10-25 15:45:00', 'DE', false),
  (11, 'Tyrell',            1, '2023-11-08 10:15:00', 'JP', false),
  (12, 'Vandelay',          1, '2023-12-19 11:50:00', 'US', true);

-- ── users: 60 total, with a UNIQUE most-users org (org 1 = 12, no tie) ──────
-- Per-org counts: 12,9,8,7,6,5,4,3,2,2,1,1  (sum = 60; max = org 1 = 12).
-- role cycles admin/member/viewer; last_active_at is NULL for every 4th user.
INSERT INTO users (organization_id, email, full_name, role, created_at, last_active_at)
SELECT o.org_id,
       'user' || gs || '_org' || o.org_id || '@example.com',
       'User ' || gs || ' of Org ' || o.org_id,
       (ARRAY['admin', 'member', 'viewer'])[1 + ((gs - 1) % 3)]::user_role,
       TIMESTAMP '2024-01-01 00:00:00' + (((o.org_id * 7) + gs) % 300) * INTERVAL '1 day',
       CASE WHEN gs % 4 = 0 THEN NULL
            ELSE TIMESTAMP '2024-06-01 00:00:00' + ((gs * 3) % 120) * INTERVAL '1 day'
       END
FROM (VALUES
        (1, 12), (2, 9), (3, 8), (4, 7), (5, 6), (6, 5),
        (7, 4),  (8, 3), (9, 2), (10, 2), (11, 1), (12, 1)
     ) AS o(org_id, cnt)
CROSS JOIN LATERAL generate_series(1, o.cnt) AS gs
ORDER BY o.org_id, gs;

-- ── subscriptions: 15, with EXACTLY 3 canceled (ids 11, 12, 13) ─────────────
-- statuses: 9 active, 2 trialing, 2 past_due, 3 canceled. canceled_at set only
-- on the canceled rows.
INSERT INTO subscriptions (id, organization_id, plan_id, status, started_at, canceled_at, seats) VALUES
  (1,   1, 4, 'active',   '2023-01-10 09:00:00', NULL,                  50),
  (2,   2, 2, 'active',   '2023-02-15 10:30:00', NULL,                  10),
  (3,   3, 2, 'active',   '2023-03-20 11:00:00', NULL,                   8),
  (4,   4, 5, 'active',   '2023-04-05 14:00:00', NULL,                 100),
  (5,   5, 3, 'active',   '2023-05-12 08:45:00', NULL,                  10),
  (6,   6, 4, 'active',   '2023-06-18 16:20:00', NULL,                  40),
  (7,   7, 3, 'trialing', '2024-07-22 13:10:00', NULL,                   5),
  (8,   9, 2, 'trialing', '2024-09-14 12:00:00', NULL,                   4),
  (9,   2, 2, 'past_due', '2023-02-15 10:30:00', NULL,                  10),
  (10,  5, 2, 'past_due', '2022-05-12 08:45:00', NULL,                   6),
  (11,  8, 1, 'canceled', '2023-08-30 09:30:00', '2024-03-01 09:00:00',  3),
  (12, 10, 1, 'canceled', '2023-10-25 15:45:00', '2024-02-10 15:00:00',  2),
  (13, 11, 1, 'canceled', '2023-11-08 10:15:00', '2024-01-20 10:00:00',  1),
  (14,  1, 4, 'active',   '2024-01-01 00:00:00', NULL,                  50),
  (15, 12, 1, 'active',   '2023-12-19 11:50:00', NULL,                   2);

-- ── usage_events: 300, bucketed to orgs 1..10 ONLY ──────────────────────────
-- => orgs 11 and 12 have ZERO usage_events (the LEFT-join / "no usage" case).
-- user_id is NULL for every 5th event (nullable FK); otherwise a valid users.id
-- in 1..60. One event per day across Jan–Oct 2024 -> a known monthly structure.
INSERT INTO usage_events (organization_id, user_id, event_type, occurred_at, quantity)
SELECT 1 + (gs % 10),                                              -- orgs 1..10
       CASE WHEN gs % 5 = 0 THEN NULL ELSE 1 + (gs % 60) END,      -- nullable FK
       (ARRAY['login', 'api_call', 'export', 'report_view'])[1 + (gs % 4)],
       TIMESTAMP '2024-01-01 00:00:00'
         + (gs % 300) * INTERVAL '1 day'
         + (gs % 24)  * INTERVAL '1 hour',
       1 + (gs % 10)
FROM generate_series(1, 300) AS gs
ORDER BY gs;

-- ── invoices: 40, with 30 paid / 6 open / 4 void ────────────────────────────
-- gs 1..30 -> paid, 31..36 -> open, 37..40 -> void (so paid count = 30).
-- amount = 100 + (gs % 10) * 50. Paid total = 3 * 3250 = 9750.00.
-- issued_at every 7 days from 2024-01-15 -> Jan–Oct 2024 buckets.
INSERT INTO invoices (organization_id, amount, status, issued_at, due_at)
SELECT 1 + (gs % 12),                                              -- orgs 1..12
       (100 + (gs % 10) * 50)::numeric(10, 2),
       (CASE WHEN gs <= 30 THEN 'paid'
             WHEN gs <= 36 THEN 'open'
             ELSE 'void' END)::invoice_status,
       TIMESTAMP '2024-01-15 00:00:00' + (gs * 7)      * INTERVAL '1 day',
       TIMESTAMP '2024-01-15 00:00:00' + (gs * 7 + 30) * INTERVAL '1 day'
FROM generate_series(1, 40) AS gs
ORDER BY gs;

-- ── payments: one per paid invoice (30 rows) ────────────────────────────────
-- payment.amount = invoice.amount, so SUM(payments) = paid revenue = 9750.00.
INSERT INTO payments (invoice_id, amount, paid_at, method)
SELECT i.id,
       i.amount,
       i.issued_at + INTERVAL '3 days',
       (ARRAY['card', 'bank_transfer', 'paypal'])[1 + (i.id % 3)]
FROM invoices i
WHERE i.status = 'paid'
ORDER BY i.id;

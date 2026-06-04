"""FIXED gold set for the SaaS honest benchmark (6.2) — the benchmark of record.

The questions are committed up front and NOT tuned to pass. Correctness is
result-equivalence (eval/result_equivalence.py) against the deterministic
nixus_saas seed (6.1): the gold_sql is the reference, the seed determines the
answer. A lower pass rate than the retired Chinook suite is expected — this is
the first untuned measurement.

Schema note: every gold_sql below was checked against the live nixus_saas schema
(organizations, plans, users, subscriptions, usage_events, invoices, payments).
The specified cases needed NO name adjustments — all table/column names matched.

Counts: 57 answerable (13 easy + 17 medium + 27 hard = 47% hard) + 10 scope.
  * 37 are the cases specified verbatim in 6.2 (E1-E10, M1-M12, H1-H15).
  * 20 were added following the same difficulty mix and schema, weighted toward
    hard (12 of the 20): E11-E13, M13-M17, H16-H27. They are NOT chosen for ease
    (more multi-hop, HAVING, LEFT-join 'none', cross-aggregate, time buckets).

Each answerable case: id, tier, question, gold_sql, ordered.
  ordered=True only when the question fixes a row order (top-N / monthly series);
  otherwise comparison is order-insensitive (multiset).
Each scope case: id, question, expected_outcome — one of
  OUT_OF_SCOPE / WRITE_REFUSAL / NEEDS_CLARIFICATION (scored on the scope gate's
  scope_category; refusals must NOT execute SQL).
"""
from __future__ import annotations

# ── ANSWERABLE — EASY (single table / simple filter / count) ─────────────────
_EASY: list[dict] = [
    {"id": "E1", "tier": "easy", "ordered": False,
     "question": "How many organizations are there?",
     "gold_sql": "SELECT count(*) FROM organizations;"},
    {"id": "E2", "tier": "easy", "ordered": False,
     "question": "List all plan names.",
     "gold_sql": "SELECT name FROM plans;"},
    {"id": "E3", "tier": "easy", "ordered": False,
     "question": "How many users have the role 'admin'?",
     "gold_sql": "SELECT count(*) FROM users WHERE role='admin';"},
    {"id": "E4", "tier": "easy", "ordered": False,
     "question": "Which organizations are inactive?",
     "gold_sql": "SELECT name FROM organizations WHERE is_active = false;"},
    {"id": "E5", "tier": "easy", "ordered": False,
     "question": "How many invoices are in 'open' status?",
     "gold_sql": "SELECT count(*) FROM invoices WHERE status='open';"},
    {"id": "E6", "tier": "easy", "ordered": False,
     "question": "What are the distinct subscription statuses?",
     "gold_sql": "SELECT DISTINCT status FROM subscriptions;"},
    {"id": "E7", "tier": "easy", "ordered": False,
     "question": "How many users are there in total?",
     "gold_sql": "SELECT count(*) FROM users;"},
    {"id": "E8", "tier": "easy", "ordered": False,
     "question": "List the plan tiers and their monthly prices.",
     "gold_sql": "SELECT tier, monthly_price FROM plans;"},
    {"id": "E9", "tier": "easy", "ordered": False,
     "question": "How many payments were made by the 'card' method?",
     "gold_sql": "SELECT count(*) FROM payments WHERE method='card';"},
    {"id": "E10", "tier": "easy", "ordered": False,
     "question": "Which countries do organizations operate in?",
     "gold_sql": "SELECT DISTINCT country FROM organizations;"},
    # ── added (3) ──
    {"id": "E11", "tier": "easy", "ordered": False,
     "question": "How many plans are there?",
     "gold_sql": "SELECT count(*) FROM plans;"},
    {"id": "E12", "tier": "easy", "ordered": False,
     "question": "List the email addresses of all users with the 'viewer' role.",
     "gold_sql": "SELECT email FROM users WHERE role='viewer';"},
    {"id": "E13", "tier": "easy", "ordered": False,
     "question": "How many subscriptions are there in total?",
     "gold_sql": "SELECT count(*) FROM subscriptions;"},
]

# ── ANSWERABLE — MEDIUM (single join / aggregation / enum + group) ───────────
_MEDIUM: list[dict] = [
    {"id": "M1", "tier": "medium", "ordered": False,
     "question": "How many users belong to each organization?",
     "gold_sql": "SELECT o.name, count(u.id) FROM organizations o "
                 "LEFT JOIN users u ON u.organization_id=o.id GROUP BY o.id, o.name;"},
    {"id": "M2", "tier": "medium", "ordered": False,
     "question": "What is the total invoice amount per organization?",
     "gold_sql": "SELECT o.name, sum(i.amount) FROM organizations o "
                 "JOIN invoices i ON i.organization_id=o.id GROUP BY o.id, o.name;"},
    {"id": "M3", "tier": "medium", "ordered": False,
     "question": "How many organizations are on each plan tier?",
     "gold_sql": "SELECT p.tier, count(o.id) FROM plans p "
                 "JOIN organizations o ON o.plan_id=p.id GROUP BY p.tier;"},
    {"id": "M4", "tier": "medium", "ordered": False,
     "question": "What is the total revenue from paid invoices?",
     "gold_sql": "SELECT sum(amount) FROM invoices WHERE status='paid';"},
    {"id": "M5", "tier": "medium", "ordered": False,
     "question": "How many active subscriptions are there per plan?",
     "gold_sql": "SELECT p.name, count(s.id) FROM plans p "
                 "JOIN subscriptions s ON s.plan_id=p.id WHERE s.status='active' "
                 "GROUP BY p.id, p.name;"},
    {"id": "M6", "tier": "medium", "ordered": False,
     "question": "List each organization and its plan tier.",
     "gold_sql": "SELECT o.name, p.tier FROM organizations o "
                 "JOIN plans p ON o.plan_id=p.id;"},
    {"id": "M7", "tier": "medium", "ordered": False,
     "question": "How many usage events did each event_type generate?",
     "gold_sql": "SELECT event_type, count(*) FROM usage_events GROUP BY event_type;"},
    {"id": "M8", "tier": "medium", "ordered": False,
     "question": "What is the average invoice amount per status?",
     "gold_sql": "SELECT status, avg(amount) FROM invoices GROUP BY status;"},
    {"id": "M9", "tier": "medium", "ordered": False,
     "question": "How many users per role?",
     "gold_sql": "SELECT role, count(*) FROM users GROUP BY role;"},
    {"id": "M10", "tier": "medium", "ordered": False,
     "question": "Total payments amount per payment method.",
     "gold_sql": "SELECT method, sum(amount) FROM payments GROUP BY method;"},
    {"id": "M11", "tier": "medium", "ordered": False,
     "question": "Which organizations have an active subscription?",
     "gold_sql": "SELECT DISTINCT o.name FROM organizations o "
                 "JOIN subscriptions s ON s.organization_id=o.id WHERE s.status='active';"},
    {"id": "M12", "tier": "medium", "ordered": False,
     "question": "Count of canceled subscriptions.",
     "gold_sql": "SELECT count(*) FROM subscriptions WHERE status='canceled';"},
    # ── added (5) ──
    {"id": "M13", "tier": "medium", "ordered": False,
     "question": "What is the total quantity of usage events per event type?",
     "gold_sql": "SELECT event_type, sum(quantity) FROM usage_events GROUP BY event_type;"},
    {"id": "M14", "tier": "medium", "ordered": False,
     "question": "How many invoices does each organization have?",
     "gold_sql": "SELECT o.name, count(i.id) FROM organizations o "
                 "JOIN invoices i ON i.organization_id=o.id GROUP BY o.id, o.name;"},
    {"id": "M15", "tier": "medium", "ordered": False,
     "question": "What is the total number of seats across active subscriptions?",
     "gold_sql": "SELECT sum(seats) FROM subscriptions WHERE status='active';"},
    {"id": "M16", "tier": "medium", "ordered": False,
     "question": "How many users were created in 2024?",
     "gold_sql": "SELECT count(*) FROM users "
                 "WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01';"},
    {"id": "M17", "tier": "medium", "ordered": False,
     "question": "List each plan name and its seat limit.",
     "gold_sql": "SELECT name, seat_limit FROM plans;"},
]

# ── ANSWERABLE — HARD (multi-hop / LEFT-join 'none' / time bucket / ranking) ──
_HARD: list[dict] = [
    {"id": "H1", "tier": "hard", "ordered": True,
     "question": "Which organization has the most users?",
     "gold_sql": "SELECT o.name, count(u.id) c FROM organizations o "
                 "LEFT JOIN users u ON u.organization_id=o.id "
                 "GROUP BY o.id, o.name ORDER BY c DESC LIMIT 1;"},
    {"id": "H2", "tier": "hard", "ordered": True,
     "question": "Top 5 organizations by total paid invoice amount.",
     "gold_sql": "SELECT o.name, sum(i.amount) s FROM organizations o "
                 "JOIN invoices i ON i.organization_id=o.id AND i.status='paid' "
                 "GROUP BY o.id, o.name ORDER BY s DESC LIMIT 5;"},
    {"id": "H3", "tier": "hard", "ordered": False,
     "question": "Which organizations have no usage events?",
     "gold_sql": "SELECT o.name FROM organizations o "
                 "LEFT JOIN usage_events e ON e.organization_id=o.id "
                 "WHERE e.id IS NULL;"},
    {"id": "H4", "tier": "hard", "ordered": False,
     "question": "Total payment amount per organization (via invoices).",
     "gold_sql": "SELECT o.name, sum(p.amount) FROM organizations o "
                 "JOIN invoices i ON i.organization_id=o.id "
                 "JOIN payments p ON p.invoice_id=i.id GROUP BY o.id, o.name;"},
    {"id": "H5", "tier": "hard", "ordered": True,
     "question": "Monthly count of usage events in 2024.",
     "gold_sql": "SELECT date_trunc('month', occurred_at) m, count(*) FROM usage_events "
                 "WHERE occurred_at >= '2024-01-01' AND occurred_at < '2025-01-01' "
                 "GROUP BY m ORDER BY m;"},
    {"id": "H6", "tier": "hard", "ordered": False,
     "question": "Which enterprise-tier organizations have more than 5 users?",
     "gold_sql": "SELECT o.name, count(u.id) c FROM organizations o "
                 "JOIN plans p ON o.plan_id=p.id "
                 "JOIN users u ON u.organization_id=o.id "
                 "WHERE p.tier='enterprise' GROUP BY o.id, o.name HAVING count(u.id) > 5;"},
    {"id": "H7", "tier": "hard", "ordered": False,
     "question": "Organizations with open invoices but no payments.",
     "gold_sql": "SELECT DISTINCT o.name FROM organizations o "
                 "JOIN invoices i ON i.organization_id=o.id AND i.status='open' "
                 "WHERE NOT EXISTS (SELECT 1 FROM payments p WHERE p.invoice_id=i.id);"},
    {"id": "H8", "tier": "hard", "ordered": False,
     "question": "Average number of seats on active subscriptions per plan tier.",
     "gold_sql": "SELECT p.tier, avg(s.seats) FROM subscriptions s "
                 "JOIN plans p ON s.plan_id=p.id WHERE s.status='active' GROUP BY p.tier;"},
    {"id": "H9", "tier": "hard", "ordered": False,
     "question": "Which users have never been active (no last_active_at)?",
     "gold_sql": "SELECT email FROM users WHERE last_active_at IS NULL;"},
    {"id": "H10", "tier": "hard", "ordered": False,
     "question": "Total revenue (paid invoices) per plan tier.",
     "gold_sql": "SELECT p.tier, sum(i.amount) FROM plans p "
                 "JOIN organizations o ON o.plan_id=p.id "
                 "JOIN invoices i ON i.organization_id=o.id AND i.status='paid' "
                 "GROUP BY p.tier;"},
    {"id": "H11", "tier": "hard", "ordered": True,
     # Determinacy fix (Step 3): usage events are uniform across the 10 active
     # orgs (all 30), so "top 3" is a 10-way tie. Added `o.id` as a deterministic
     # tiebreaker so the REFERENCE is well-defined. Intent/difficulty unchanged
     # and NOT made easier — H11 is ambiguous on this seed and is expected to
     # fail unless the system reproduces the same tiebreak (an honest finding).
     "question": "Top 3 organizations by usage event count.",
     "gold_sql": "SELECT o.name, count(e.id) c FROM organizations o "
                 "JOIN usage_events e ON e.organization_id=o.id "
                 "GROUP BY o.id, o.name ORDER BY c DESC, o.id LIMIT 3;"},
    {"id": "H12", "tier": "hard", "ordered": False,
     "question": "Organizations whose total invoiced amount exceeds 1000.",
     "gold_sql": "SELECT o.name, sum(i.amount) s FROM organizations o "
                 "JOIN invoices i ON i.organization_id=o.id "
                 "GROUP BY o.id, o.name HAVING sum(i.amount) > 1000;"},
    {"id": "H13", "tier": "hard", "ordered": True,
     "question": "Count of users created in each month of 2024.",
     "gold_sql": "SELECT date_trunc('month', created_at) m, count(*) FROM users "
                 "WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01' "
                 "GROUP BY m ORDER BY m;"},
    {"id": "H14", "tier": "hard", "ordered": False,
     "question": "Which plans have no organizations assigned?",
     "gold_sql": "SELECT p.name FROM plans p "
                 "LEFT JOIN organizations o ON o.plan_id=p.id WHERE o.id IS NULL;"},
    {"id": "H15", "tier": "hard", "ordered": False,
     "question": "For each organization, the number of distinct event types used.",
     "gold_sql": "SELECT o.name, count(DISTINCT e.event_type) FROM organizations o "
                 "JOIN usage_events e ON e.organization_id=o.id GROUP BY o.id, o.name;"},
    # ── added (12) — weighted toward multi-hop / HAVING / cross-aggregate ──
    {"id": "H16", "tier": "hard", "ordered": False,
     "question": "Which organizations have more than 3 invoices?",
     "gold_sql": "SELECT o.name, count(i.id) c FROM organizations o "
                 "JOIN invoices i ON i.organization_id=o.id "
                 "GROUP BY o.id, o.name HAVING count(i.id) > 3;"},
    {"id": "H17", "tier": "hard", "ordered": True,
     "question": "Top 2 organizations by number of users.",
     "gold_sql": "SELECT o.name, count(u.id) c FROM organizations o "
                 "JOIN users u ON u.organization_id=o.id "
                 "GROUP BY o.id, o.name ORDER BY c DESC LIMIT 2;"},
    {"id": "H18", "tier": "hard", "ordered": False,
     "question": "Total amount paid per organization, for organizations that have made payments.",
     "gold_sql": "SELECT o.name, sum(p.amount) FROM organizations o "
                 "JOIN invoices i ON i.organization_id=o.id "
                 "JOIN payments p ON p.invoice_id=i.id GROUP BY o.id, o.name;"},
    {"id": "H19", "tier": "hard", "ordered": False,
     "question": "How many distinct organizations have usage events?",
     "gold_sql": "SELECT count(DISTINCT organization_id) FROM usage_events;"},
    {"id": "H20", "tier": "hard", "ordered": False,
     "question": "For each plan tier, the number of distinct organizations.",
     "gold_sql": "SELECT p.tier, count(DISTINCT o.id) FROM plans p "
                 "JOIN organizations o ON o.plan_id=p.id GROUP BY p.tier;"},
    {"id": "H21", "tier": "hard", "ordered": False,
     "question": "Which users belong to organizations on the 'enterprise' tier?",
     "gold_sql": "SELECT u.email FROM users u "
                 "JOIN organizations o ON u.organization_id=o.id "
                 "JOIN plans p ON o.plan_id=p.id WHERE p.tier='enterprise';"},
    {"id": "H22", "tier": "hard", "ordered": True,
     "question": "Monthly total of paid invoice amounts in 2024.",
     "gold_sql": "SELECT date_trunc('month', issued_at) m, sum(amount) FROM invoices "
                 "WHERE status='paid' AND issued_at >= '2024-01-01' AND issued_at < '2025-01-01' "
                 "GROUP BY m ORDER BY m;"},
    {"id": "H23", "tier": "hard", "ordered": False,
     "question": "Organizations with total paid revenue greater than 500.",
     "gold_sql": "SELECT o.name, sum(i.amount) s FROM organizations o "
                 "JOIN invoices i ON i.organization_id=o.id AND i.status='paid' "
                 "GROUP BY o.id, o.name HAVING sum(i.amount) > 500;"},
    {"id": "H24", "tier": "hard", "ordered": False,
     "question": "Average payment amount per payment method.",
     "gold_sql": "SELECT method, avg(amount) FROM payments GROUP BY method;"},
    {"id": "H25", "tier": "hard", "ordered": False,
     "question": "Which organizations have users but no usage events?",
     "gold_sql": "SELECT DISTINCT o.name FROM organizations o "
                 "JOIN users u ON u.organization_id=o.id "
                 "WHERE NOT EXISTS (SELECT 1 FROM usage_events e WHERE e.organization_id=o.id);"},
    {"id": "H26", "tier": "hard", "ordered": False,
     "question": "For each event type, the average quantity per event.",
     "gold_sql": "SELECT event_type, avg(quantity) FROM usage_events GROUP BY event_type;"},
    {"id": "H27", "tier": "hard", "ordered": False,
     "question": "Which organizations have more users than invoices?",
     "gold_sql": "SELECT o.name FROM organizations o "
                 "JOIN (SELECT organization_id, count(*) uc FROM users GROUP BY organization_id) u "
                 "  ON u.organization_id=o.id "
                 "LEFT JOIN (SELECT organization_id, count(*) ic FROM invoices GROUP BY organization_id) i "
                 "  ON i.organization_id=o.id "
                 "WHERE u.uc > coalesce(i.ic, 0);"},
]

ANSWERABLE: list[dict] = _EASY + _MEDIUM + _HARD

# ── SCOPE / REFUSAL (must NOT produce SQL; scored on scope_category outcome) ──
_DOCKER_COMPOSE_WITH_ERROR = """version: "3.9"
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: secret
ERROR: yaml: line 7: did not find expected key
"""

_PYTHON_TRACEBACK = """Traceback (most recent call last):
  File "app.py", line 42, in <module>
    main()
  File "app.py", line 30, in main
    result = compute(x)
ZeroDivisionError: division by zero
"""

SCOPE: list[dict] = [
    {"id": "S1", "question": "docker compose up -d", "expected_outcome": "OUT_OF_SCOPE"},
    {"id": "S2", "question": _DOCKER_COMPOSE_WITH_ERROR, "expected_outcome": "OUT_OF_SCOPE"},
    {"id": "S3", "question": _PYTHON_TRACEBACK, "expected_outcome": "OUT_OF_SCOPE"},
    {"id": "S4", "question": "delete all users", "expected_outcome": "WRITE_REFUSAL"},
    {"id": "S5", "question": "drop the invoices table", "expected_outcome": "WRITE_REFUSAL"},
    {"id": "S6", "question": "update organizations set is_active = true", "expected_outcome": "WRITE_REFUSAL"},
    {"id": "S7", "question": "show me the top ones", "expected_outcome": "NEEDS_CLARIFICATION"},
    {"id": "S8", "question": "what about the good customers", "expected_outcome": "NEEDS_CLARIFICATION"},
    {"id": "S9", "question": "how are things going", "expected_outcome": "OUT_OF_SCOPE"},
    {"id": "S10", "question": "give me the stuff", "expected_outcome": "NEEDS_CLARIFICATION"},
]


def tier_counts() -> dict:
    counts = {"easy": 0, "medium": 0, "hard": 0}
    for c in ANSWERABLE:
        counts[c["tier"]] += 1
    return counts

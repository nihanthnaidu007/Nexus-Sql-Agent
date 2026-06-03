-- ============================================================================
-- Adversarial schema for testing nixus/schema/introspect.py (prompt 2.2).
--
-- Deliberately nasty: multiple schemas, a 50+ column table, a COMPOSITE primary
-- key and a COMPOSITE foreign key (with the ordering trap built in), a single
-- FK, a cross-schema FK, plus array / enum / jsonb / numeric type fidelity and
-- nullable/NOT NULL coverage, and table+column comments.
--
-- ORDERING TRAPS (the #1 introspection bug — column pairing/order):
--   * public.parent declares its columns physically as (parent_code, tenant_id)
--     but its PRIMARY KEY is (tenant_id, parent_code) — PK order != attnum order.
--   * public.child declares columns physically as (.., p_parent_code, p_tenant_id)
--     but its composite FK lists (p_tenant_id, p_parent_code) -> parent(tenant_id,
--     parent_code) — FK order != attnum order, and column NAMES differ from the
--     referenced names.
-- An implementation that orders PK/FK columns by attnum (instead of by the
-- constraint's own ordinal arrays) produces the WRONG pairing and the test fails.
-- ============================================================================

-- A second user schema (in addition to public). Tables live in BOTH.
CREATE SCHEMA billing;

-- ── Composite PRIMARY KEY, PK order != physical column order ─────────────────
CREATE TABLE public.parent (
    parent_code text    NOT NULL,   -- attnum 1
    tenant_id   integer NOT NULL,   -- attnum 2
    label       text                -- attnum 3, NULLABLE
    , PRIMARY KEY (tenant_id, parent_code)   -- ordered ['tenant_id','parent_code']
);
COMMENT ON TABLE  public.parent       IS 'Parent table with a composite primary key.';
COMMENT ON COLUMN public.parent.label IS 'Human-readable parent label.';

-- ── Enum type + array + jsonb + numeric + nullable/NOT NULL ──────────────────
CREATE TYPE public.order_status AS ENUM ('active', 'cancelled', 'trial');

CREATE TABLE public.orders (
    order_id serial              PRIMARY KEY,
    status   public.order_status NOT NULL,   -- enum, NOT NULL
    tags     text[],                         -- ARRAY, nullable
    metadata jsonb,                          -- JSONB, nullable
    amount   numeric(12,2)       NOT NULL,   -- NUMERIC(p,s), NOT NULL
    note     text                            -- nullable
);
COMMENT ON TABLE  public.orders        IS 'Orders with enum/array/jsonb/numeric columns.';
COMMENT ON COLUMN public.orders.status IS 'Lifecycle status of the order.';

-- ── Composite FK (order trap) + a simple single-column FK ────────────────────
CREATE TABLE public.child (
    child_id      serial  PRIMARY KEY,  -- attnum 1
    p_parent_code text    NOT NULL,     -- attnum 2  (physically BEFORE p_tenant_id)
    p_tenant_id   integer NOT NULL,     -- attnum 3
    order_id      integer,              -- attnum 4, nullable
    CONSTRAINT child_parent_fk
        FOREIGN KEY (p_tenant_id, p_parent_code)
        REFERENCES public.parent (tenant_id, parent_code),
    CONSTRAINT child_order_fk
        FOREIGN KEY (order_id) REFERENCES public.orders (order_id)
);

-- ── Wide table: 61 columns (id + col_001..col_060), nothing may be truncated ─
CREATE TABLE public.wide_table (
    id integer PRIMARY KEY,
    col_001 text, col_002 text, col_003 text, col_004 text, col_005 text,
    col_006 text, col_007 text, col_008 text, col_009 text, col_010 text,
    col_011 text, col_012 text, col_013 text, col_014 text, col_015 text,
    col_016 text, col_017 text, col_018 text, col_019 text, col_020 text,
    col_021 text, col_022 text, col_023 text, col_024 text, col_025 text,
    col_026 text, col_027 text, col_028 text, col_029 text, col_030 text,
    col_031 text, col_032 text, col_033 text, col_034 text, col_035 text,
    col_036 text, col_037 text, col_038 text, col_039 text, col_040 text,
    col_041 text, col_042 text, col_043 text, col_044 text, col_045 text,
    col_046 text, col_047 text, col_048 text, col_049 text, col_050 text,
    col_051 text, col_052 text, col_053 text, col_054 text, col_055 text,
    col_056 text, col_057 text, col_058 text, col_059 text, col_060 text
);

-- ── Cross-schema FK: billing.invoice.order_id -> public.orders.order_id ──────
CREATE TABLE billing.invoice (
    invoice_id serial      PRIMARY KEY,
    order_id   integer     NOT NULL,
    issued_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT billing_invoice_order_fk
        FOREIGN KEY (order_id) REFERENCES public.orders (order_id)
);
COMMENT ON TABLE billing.invoice IS 'Billing invoices, in a separate schema.';

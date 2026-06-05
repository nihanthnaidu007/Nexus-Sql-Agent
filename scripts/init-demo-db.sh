#!/usr/bin/env bash
# ============================================================================
# Phase 15 — Provision the DEMO target: the RICH SaaS sample (nixus_saas_demo).
#
# Runs ONCE on a fresh Postgres volume, from /docker-entrypoint-initdb.d/, AFTER
# 10-init-target-db.sql created the read-only role `nixus_readonly` (the `30`
# prefix orders it after `10` and after `20-init-saas-db.sh`). It makes
# `docker compose up` open a RICH demo: the demo target is created, loaded with
# the time-spread demo seed, and granted read-only — so the very first query in
# the UI draws compelling multi-row / time-series charts with NO manual step.
#
# This is the DEMO counterpart of 20-init-saas-db.sh. It is a SEPARATE database
# (nixus_saas_demo) loaded from a SEPARATE seed (eval/saas_demo_seed.sql) — the
# frozen benchmark database (nixus_saas) is provisioned independently by
# 20-init-saas-db.sh and is never touched here. The role stays STRICTLY read-only
# here too: SELECT only, never INSERT/UPDATE/DELETE/DDL.
#
# Only applied on a fresh init: `docker compose down -v && docker compose up`.
# ============================================================================
set -euo pipefail

echo "◈ [init] Provisioning the RICH demo target (nixus_saas_demo)..."

# Create the demo database and let the read-only role connect.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-'EOSQL'
    CREATE DATABASE nixus_saas_demo;
    GRANT CONNECT ON DATABASE nixus_saas_demo TO nixus_readonly;
EOSQL

# Load the SAME schema as the benchmark, then the deterministic RICH demo seed
# (both mounted read-only at /opt/nixus-saas).
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname nixus_saas_demo \
    -f /opt/nixus-saas/saas_schema.sql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname nixus_saas_demo \
    -f /opt/nixus-saas/saas_demo_seed.sql

# SELECT-only grant pattern — identical to init-saas-db.sh / rebuild_demo_db.py.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname nixus_saas_demo <<-'EOSQL'
    GRANT USAGE ON SCHEMA public TO nixus_readonly;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO nixus_readonly;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO nixus_readonly;
EOSQL

echo "◈ [init] nixus_saas_demo ready (schema + rich demo seed), read-only to nixus_readonly."

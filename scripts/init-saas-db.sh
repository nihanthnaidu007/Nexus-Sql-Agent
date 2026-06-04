#!/usr/bin/env bash
# ============================================================================
# 7.2 — Provision the DEFAULT target: the bundled SaaS sample (nixus_saas).
#
# Runs ONCE on a fresh Postgres volume, from /docker-entrypoint-initdb.d/, AFTER
# 10-init-target-db.sql has created the read-only role `nixus_readonly` (the `20`
# prefix orders it after `10`). It makes `docker compose up` self-contained: the
# default SaaS target is created, loaded, seeded, and granted read-only — so the
# very first query works with NO manual step and NO connection string.
#
# It loads the SAME single-source-of-truth files scripts/rebuild_saas_db.py uses
# (eval/saas_schema.sql + eval/saas_seed.sql, mounted read-only at /opt/nixus-saas),
# so the data is byte-identical to the benchmark's. The role stays STRICTLY
# read-only here too: SELECT only, never INSERT/UPDATE/DELETE/DDL.
#
# Only applied on a fresh init: `docker compose down -v && docker compose up`.
# ============================================================================
set -euo pipefail

echo "◈ [init] Provisioning the default SaaS sample target (nixus_saas)..."

# Create the SaaS database and let the read-only role connect.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-'EOSQL'
    CREATE DATABASE nixus_saas;
    GRANT CONNECT ON DATABASE nixus_saas TO nixus_readonly;
EOSQL

# Load the deterministic schema + seed (single source of truth, mounted r/o).
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname nixus_saas \
    -f /opt/nixus-saas/saas_schema.sql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname nixus_saas \
    -f /opt/nixus-saas/saas_seed.sql

# SELECT-only grant pattern — identical to init-target-db.sql / rebuild_saas_db.py.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname nixus_saas <<-'EOSQL'
    GRANT USAGE ON SCHEMA public TO nixus_readonly;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO nixus_readonly;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO nixus_readonly;
EOSQL

echo "◈ [init] nixus_saas ready (schema + deterministic seed), read-only to nixus_readonly."

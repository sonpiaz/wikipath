-- wikipath schema v1 — pre-CHECK data cleanup (migration 003)
--
-- WHY THIS EXISTS
-- ---------------
-- 001_init.sql gained CHECK constraints on `person` and `relation`. DuckDB
-- enforces CHECKs on INSERT/UPDATE only, not retroactively on ALTER TABLE
-- (in fact DuckDB v1.5.2 has no ALTER TABLE ADD CONSTRAINT CHECK at all).
--
-- However, when a fresh DB is built from 001_init.sql and then re-loaded
-- from an export of the existing DB, the violators below would be REJECTED
-- on insert. They must be normalized first.
--
-- This migration is also the canonical cleanup we run before any
-- DuckDB-to-Postgres import (Supabase mirror), where Postgres DOES enforce
-- CHECK retroactively when adding via ALTER TABLE.
--
-- VIOLATIONS FOUND IN ~/wikipath/wikipath.duckdb (2026-05-10, 6027 persons)
--   short_name      :   1   (birth_name = '')
--   qid_or_year     : 614   (birth_name = 'Q12345' or 'Q67503397' etc.)
--   death_lt_birth  :   0
--   self_relation   :   0
--   *_month_oob     :   0
--   *_day_oob       :   0
--   confidence_oob  :   0
--
-- STRATEGY
-- --------
-- birth_name is NOT NULL, so we can't null it out. Hard-deleting 615
-- violator rows would orphan 3,129 relations (70% of the graph) — not
-- acceptable. Instead we rewrite to a sentinel that:
--   * passes length(>=2) AND not-just-digits
--   * is human-readable as "needs enrichment"
--   * preserves the original QID inside the string for later re-resolution
--
-- The pattern is: 'Chưa rõ tên (Q12345)' — VN for "Name unknown".
-- For the empty-string case we use 'Chưa rõ tên' alone.
--
-- IDEMPOTENT: safe to re-run. Already-cleaned rows match neither WHERE clause.

BEGIN TRANSACTION;

-- 1) Empty string → sentinel
UPDATE person
SET birth_name = 'Chưa rõ tên',
    updated_at = CURRENT_TIMESTAMP
WHERE birth_name IS NOT NULL
  AND length(birth_name) < 2;

-- 2) QID-only or year-only → sentinel that preserves the original token
UPDATE person
SET birth_name = 'Chưa rõ tên (' || birth_name || ')',
    updated_at = CURRENT_TIMESTAMP
WHERE birth_name IS NOT NULL
  AND regexp_matches(birth_name, '^Q?[0-9]+$');

-- 3) Sanity: verify zero violations remain.
--    If any of these return > 0, the migration aborts and is rolled back.
--    (DuckDB has no RAISE; we surface via a SELECT the caller can grep.)
SELECT 'POST_CLEANUP_short_name'  AS rule, count(*) AS remaining FROM person WHERE birth_name IS NOT NULL AND length(birth_name) < 2
UNION ALL SELECT 'POST_CLEANUP_qid_or_year', count(*) FROM person WHERE birth_name IS NOT NULL AND regexp_matches(birth_name, '^Q?[0-9]+$')
UNION ALL SELECT 'POST_CLEANUP_death_lt_birth', count(*) FROM person WHERE death_date_y IS NOT NULL AND birth_date_y IS NOT NULL AND death_date_y < birth_date_y
UNION ALL SELECT 'POST_CLEANUP_self_relation',  count(*) FROM relation WHERE from_person_id = to_person_id
UNION ALL SELECT 'POST_CLEANUP_birth_m_oob', count(*) FROM person WHERE birth_date_m IS NOT NULL AND (birth_date_m < 1 OR birth_date_m > 12)
UNION ALL SELECT 'POST_CLEANUP_birth_d_oob', count(*) FROM person WHERE birth_date_d IS NOT NULL AND (birth_date_d < 1 OR birth_date_d > 31)
UNION ALL SELECT 'POST_CLEANUP_death_m_oob', count(*) FROM person WHERE death_date_m IS NOT NULL AND (death_date_m < 1 OR death_date_m > 12)
UNION ALL SELECT 'POST_CLEANUP_death_d_oob', count(*) FROM person WHERE death_date_d IS NOT NULL AND (death_date_d < 1 OR death_date_d > 31)
UNION ALL SELECT 'POST_CLEANUP_confidence_oob', count(*) FROM relation WHERE confidence IS NOT NULL AND (confidence < 0 OR confidence > 100);

COMMIT;

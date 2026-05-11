-- Pre-enrichment data cleanup, derived from data/quality_report.{md,json}.
--
-- Run inside a single transaction so a failure rolls back cleanly:
--   duckdb wikipath.duckdb -c ".read scripts/cleanup_quality_issues.sql"
--
-- Idempotent: re-running after the first pass is a no-op (DELETE matches 0,
-- UPDATE matches 0). Safe to ship as part of the deploy script.

BEGIN TRANSACTION;

-- ── 1. Drop garbage names (615 records as of 2026-05-10) ──────────────
-- These are Q-only ("Q12345") or year-only ("1949") placeholders left over
-- from Wikidata imports where the label never resolved. They are filtered
-- out at display already but still occupy enrichment slots and pollute
-- search ranking. None of them carry a Wikipedia VN URL (otherwise the
-- import would have used the article title), so there is nothing to
-- recover by keeping them.
--
-- We also drop their relations so the relation table doesn't carry FK
-- dangling pointers. (DuckDB has no FK enforcement, but consistency
-- matters for the read path.)
DELETE FROM relation
WHERE from_person_id IN (
    SELECT id FROM person
    WHERE birth_name IS NOT NULL
      AND (regexp_matches(birth_name, '^Q?[0-9]+$') OR length(birth_name) < 2)
)
OR to_person_id IN (
    SELECT id FROM person
    WHERE birth_name IS NOT NULL
      AND (regexp_matches(birth_name, '^Q?[0-9]+$') OR length(birth_name) < 2)
);

DELETE FROM person
WHERE birth_name IS NOT NULL
  AND (regexp_matches(birth_name, '^Q?[0-9]+$') OR length(birth_name) < 2);

-- ── 2. Re-bucket era when it disagrees with birth_date_y (61 records) ─
-- Re-derive era from the year, overriding whatever the importer set.
-- This is purely a display fix — it does not change relations or IDs.
UPDATE person
SET era = CASE
    WHEN birth_date_y < 1500 THEN 'pre-1500'
    WHEN birth_date_y < 1900 THEN '1500-1900'
    WHEN birth_date_y < 1950 THEN '1900-1950'
    ELSE '1950+'
END
WHERE birth_date_y IS NOT NULL
  AND era IS NOT NULL
  AND (
    (era = 'pre-1500'  AND birth_date_y >= 1500) OR
    (era = '1500-1900' AND (birth_date_y < 1500 OR birth_date_y >= 1900)) OR
    (era = '1900-1950' AND (birth_date_y < 1900 OR birth_date_y >= 1950)) OR
    (era = '1950+'     AND birth_date_y < 1950)
  );

COMMIT;

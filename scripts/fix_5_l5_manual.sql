-- Manual fix for the 5 L5 cross-source year disagreements surfaced by
-- scripts/test_enrichment.py on 2026-05-12. Each row's bio prose quotes
-- a year that disagrees with the LLM-extracted structured year. Per
-- policy A ("Wikipedia wins"), align DB to whatever the bio prose says
-- because that is what the end user reads in the modal.
--
-- All five cases come from Wikipedia VN internal inconsistency (infobox
-- vs lead sentence). Manual fix here is cheaper than re-prompting the
-- LLM with stricter consistency rules.
--
-- Idempotent: re-running matches 0 rows after first apply.

BEGIN TRANSACTION;

-- 1. Nguyễn Lạc Hóa  — DB 1908/NULL → bio "(1901-1993)"
--    7y birth gap + bio has death year that DB lacks. Backfill death.
UPDATE person
SET birth_date_y = 1901, death_date_y = 1993
WHERE id = '9ffd1bac-f0dd-510e-aa7c-a90d33769ee4';

-- 2. Nguyễn Phan Long — DB 1889 → bio "(1888 – 1960)". 1y.
UPDATE person SET birth_date_y = 1888
WHERE id = 'bb59f38c-86a3-5254-a6c9-4101ddda554d';

-- 3. Lê Thần Tông — DB 1607 → bio "(1608-1662)". 1y.
UPDATE person SET birth_date_y = 1608
WHERE id = '6d8f50e4-b666-5028-89c2-66f9b0e37fb8';

-- 4. Trần Văn Trà — DB 1918 → bio "(1919-1996)". 1y.
UPDATE person SET birth_date_y = 1919
WHERE id = 'a50be6fb-5c35-54af-bc1f-507b430f3134';

-- 5. Trần Hữu Dũng — DB 1946 → bio "(1945–2023)". 1y.
UPDATE person SET birth_date_y = 1945
WHERE id = '0088a7e9-3cbe-5ce3-b8a5-91517008025b';

COMMIT;

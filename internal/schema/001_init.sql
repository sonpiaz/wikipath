-- wikipath schema v1
-- DuckDB read-path schema. Postgres equivalent will mirror this.
--
-- DIRECTION CONVENTION (important):
--   relation.from_person_id is always the SUBJECT.
--   relation.to_person_id   is always the OBJECT/TARGET.
--
--   Read as: "<from> has <kind> <to>".
--
--   Examples:
--     HCM        parent_father    Nguyễn Sinh Sắc       (HCM's father IS Sắc)
--     HCM        parent_mother    Hoàng Thị Loan        (HCM's mother IS Loan)
--     Gia Long   child_birth      Minh Mạng             (Gia Long's birth child IS Minh Mạng)
--     Gia Long   spouse           Nam Phương (rank=1)   (Gia Long has wife Nam Phương)
--     Lê Lợi     sibling_full     Lê Học                (Lê Lợi has sibling Lê Học)
--
--   We do NOT store both directions. Views below compute the inverse on read.

CREATE TABLE IF NOT EXISTS person (
    id                       UUID PRIMARY KEY,
    wikidata_qid             VARCHAR,
    wikipedia_vi_url         VARCHAR,
    birth_name               VARCHAR NOT NULL,
    current_family_name      VARCHAR,
    original_family_name     VARCHAR,
    lineage_branch           VARCHAR,
    era                      VARCHAR NOT NULL,
    dynasty                  VARCHAR,
    birth_date_y             INTEGER,
    birth_date_m             INTEGER,
    birth_date_d             INTEGER,
    death_date_y             INTEGER,
    death_date_m             INTEGER,
    death_date_d             INTEGER,
    birth_place              VARCHAR,
    death_place              VARCHAR,
    bio_short                VARCHAR,
    bio_full                 VARCHAR,
    avatar_url               VARCHAR,
    historicity              VARCHAR DEFAULT 'confirmed',
    gender                   VARCHAR DEFAULT 'unknown',
    is_living                BOOLEAN DEFAULT FALSE,
    consent_status           VARCHAR DEFAULT 'public',
    trust_score              INTEGER DEFAULT 50,
    primary_source           VARCHAR,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_person_qid    ON person(wikidata_qid);
CREATE INDEX IF NOT EXISTS idx_person_era    ON person(era);
CREATE INDEX IF NOT EXISTS idx_person_dyn    ON person(dynasty);
CREATE INDEX IF NOT EXISTS idx_person_family ON person(current_family_name);
CREATE INDEX IF NOT EXISTS idx_person_name   ON person(birth_name);

CREATE TABLE IF NOT EXISTS name (
    id            UUID PRIMARY KEY,
    person_id     UUID NOT NULL,  -- logical FK to person(id); FKs disabled
                                  -- because DuckDB blocks UPDATE on the parent
                                  -- table whenever children reference it.
    name          VARCHAR NOT NULL,
    kind          VARCHAR NOT NULL,
    period_start  INTEGER,
    period_end    INTEGER,
    language      VARCHAR DEFAULT 'vi'
);

CREATE INDEX IF NOT EXISTS idx_name_person ON name(person_id);
CREATE INDEX IF NOT EXISTS idx_name_value  ON name(name);

CREATE TABLE IF NOT EXISTS relation (
    id              UUID PRIMARY KEY,
    from_person_id  UUID NOT NULL,  -- logical FK to person(id); see name table note
    to_person_id    UUID NOT NULL,
    kind            VARCHAR NOT NULL,
    rank            INTEGER,
    period_start_y  INTEGER,
    period_end_y    INTEGER,
    source_kind     VARCHAR DEFAULT 'community',
    source_ref      VARCHAR,
    confidence      INTEGER DEFAULT 70,
    created_by      UUID,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_relation_from ON relation(from_person_id);
CREATE INDEX IF NOT EXISTS idx_relation_to   ON relation(to_person_id);
CREATE INDEX IF NOT EXISTS idx_relation_kind ON relation(kind);

CREATE TABLE IF NOT EXISTS contributor (
    id                  UUID PRIMARY KEY,
    email               VARCHAR UNIQUE,
    display_name        VARCHAR,
    lineage_affiliation VARCHAR,
    trust_tier          INTEGER DEFAULT 0,
    cla_signed_at       TIMESTAMP,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contribution_log (
    id              UUID PRIMARY KEY,
    contributor_id  UUID,
    entity_type     VARCHAR,
    entity_id       UUID,
    kind            VARCHAR,
    before_payload  JSON,
    after_payload   JSON,
    status          VARCHAR DEFAULT 'auto_approved',
    reviewed_by     UUID,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Views: parent / child / spouse / sibling lookup
-- Each view returns one row per (subject, related) pair, with kind detail.

CREATE OR REPLACE VIEW v_parents AS
SELECT
    r.from_person_id AS person_id,
    r.to_person_id   AS parent_id,
    CASE r.kind
        WHEN 'parent_father' THEN 'father'
        WHEN 'parent_mother' THEN 'mother'
    END              AS parent_kind,
    r.source_kind, r.confidence
FROM relation r
WHERE r.kind IN ('parent_father', 'parent_mother');

-- Children: inverse of v_parents PLUS explicit child_* kinds (adopted/step/foster).
-- Direction convention reminder:
--   parent_*  : from=child,  to=parent   (used for biological)
--   child_*   : from=parent, to=child    (used for adopted/step/foster)
-- The view normalizes both into (person_id=parent, child_id=child).
CREATE OR REPLACE VIEW v_children AS
-- biological children: invert parent_* edges
SELECT
    r.to_person_id   AS person_id,
    r.from_person_id AS child_id,
    'biological'     AS child_kind,
    r.source_kind, r.confidence
FROM relation r
WHERE r.kind IN ('parent_father', 'parent_mother')
UNION ALL
-- adopted/step/foster children: keep direction
SELECT
    r.from_person_id AS person_id,
    r.to_person_id   AS child_id,
    CASE r.kind
        WHEN 'child_adopted' THEN 'adopted'
        WHEN 'child_step'    THEN 'step'
        WHEN 'child_foster'  THEN 'foster'
    END              AS child_kind,
    r.source_kind, r.confidence
FROM relation r
WHERE r.kind IN ('child_adopted', 'child_step', 'child_foster');

CREATE OR REPLACE VIEW v_spouses AS
SELECT
    r.from_person_id AS person_id,
    r.to_person_id   AS spouse_id,
    r.kind           AS spouse_kind,
    r.rank,
    r.period_start_y, r.period_end_y,
    r.source_kind, r.confidence
FROM relation r
WHERE r.kind IN ('spouse', 'concubine')
UNION ALL
SELECT
    r.to_person_id   AS person_id,
    r.from_person_id AS spouse_id,
    r.kind           AS spouse_kind,
    r.rank,
    r.period_start_y, r.period_end_y,
    r.source_kind, r.confidence
FROM relation r
WHERE r.kind IN ('spouse', 'concubine');

CREATE OR REPLACE VIEW v_siblings AS
SELECT
    r.from_person_id AS person_id,
    r.to_person_id   AS sibling_id,
    r.kind           AS sibling_kind,
    r.source_kind, r.confidence
FROM relation r
WHERE r.kind IN ('sibling_full', 'sibling_paternal', 'sibling_maternal')
UNION ALL
SELECT
    r.to_person_id   AS person_id,
    r.from_person_id AS sibling_id,
    r.kind           AS sibling_kind,
    r.source_kind, r.confidence
FROM relation r
WHERE r.kind IN ('sibling_full', 'sibling_paternal', 'sibling_maternal');

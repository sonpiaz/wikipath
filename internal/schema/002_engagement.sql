-- wikipath schema v1 — engagement analytics (F8)
--
-- Adds day-1 user-behavior tracking so we can:
--   * prioritize which persons get enriched next (popularity-driven queue)
--   * surface trending people on the landing page
--   * power future investor / community analytics
--
-- No PII: session_id is a random uuid generated client-side, IPs are never
-- stored (only the 2-char ISO country derived from CF-IPCountry header), and
-- user_agent is hashed (sha1) at insert time.
--
-- Retention: 90 days of raw events. Older events are folded into
-- person_popularity by the nightly refresh job and hard-deleted.
--
-- See SPEC §17 for the full design (event taxonomy, scoring algorithm,
-- backend endpoints, FE instrumentation, privacy stance).

CREATE TABLE IF NOT EXISTS event (
    id              UUID PRIMARY KEY,
    event_type      VARCHAR NOT NULL,   -- page_view / search / modal_open / tree_expand / node_click / external_click
    person_id       UUID,               -- nullable: search-without-result has no target
    query           VARCHAR,            -- nullable: only set for `search` events
    session_id      VARCHAR NOT NULL,   -- anonymous uuid generated client-side
    referrer        VARCHAR,            -- host only, no full URL
    user_agent_hash VARCHAR(40),        -- sha1(UA); raw UA discarded at insert
    country         VARCHAR(2),         -- ISO-3166-1 alpha-2 from CF-IPCountry
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_event_person_time  ON event(person_id, created_at);
CREATE INDEX IF NOT EXISTS idx_event_type_time    ON event(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_event_session      ON event(session_id);
CREATE INDEX IF NOT EXISTS idx_event_created      ON event(created_at);

-- Materialized score table. Refreshed nightly by `cmd/refresh-popularity`.
-- The app reads from here; never reads `event` directly for hot paths.
CREATE TABLE IF NOT EXISTS person_popularity (
    person_id           UUID PRIMARY KEY,
    views_24h           INTEGER DEFAULT 0,
    views_7d            INTEGER DEFAULT 0,
    views_30d           INTEGER DEFAULT 0,
    modal_opens_30d     INTEGER DEFAULT 0,
    tree_expands_30d    INTEGER DEFAULT 0,
    external_clicks_30d INTEGER DEFAULT 0,
    unique_visitors_30d INTEGER DEFAULT 0,
    last_event_at       TIMESTAMP,
    score               REAL DEFAULT 0,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pop_score        ON person_popularity(score DESC);
CREATE INDEX IF NOT EXISTS idx_pop_last_event   ON person_popularity(last_event_at DESC);

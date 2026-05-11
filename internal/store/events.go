package store

import (
	"context"
	"crypto/sha1"
	"database/sql"
	"encoding/hex"
	"fmt"
	"net/url"
	"regexp"

	"github.com/google/uuid"
)

// ─────────── Event ingest (F8) ───────────

var sessionIDRe = regexp.MustCompile(
	`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`,
)

var validEventTypes = map[string]bool{
	"page_view":       true,
	"search":          true,
	"modal_open":      true,
	"tree_expand":     true,
	"node_click":      true,
	"external_click":  true,
}

// EventInput is the wire-format an event POSTed by the FE tracker.
type EventInput struct {
	EventType string  `json:"event_type"`
	PersonID  *string `json:"person_id,omitempty"`
	Query     *string `json:"query,omitempty"`
	SessionID string  `json:"session_id"`
	Referrer  *string `json:"referrer,omitempty"`
}

// IsValid returns nil if the input passes the day-1 validation rules,
// otherwise an error describing the first failing field.
func (e *EventInput) IsValid() error {
	if !validEventTypes[e.EventType] {
		return fmt.Errorf("invalid event_type %q", e.EventType)
	}
	if !sessionIDRe.MatchString(e.SessionID) {
		return fmt.Errorf("session_id must be uuid")
	}
	if e.PersonID != nil && *e.PersonID == "" {
		e.PersonID = nil
	}
	if e.Query != nil {
		if len(*e.Query) > 200 {
			trimmed := (*e.Query)[:200]
			e.Query = &trimmed
		}
	}
	if e.Referrer != nil {
		if h := refererHost(*e.Referrer); h != "" {
			e.Referrer = &h
		} else {
			e.Referrer = nil
		}
	}
	return nil
}

func refererHost(raw string) string {
	if raw == "" {
		return ""
	}
	u, err := url.Parse(raw)
	if err != nil || u.Host == "" {
		return ""
	}
	return u.Host
}

func hashUA(ua string) string {
	if ua == "" {
		return ""
	}
	h := sha1.Sum([]byte(ua))
	return hex.EncodeToString(h[:])
}

// resolvePersonID accepts either a wikidata QID ("Q36014") or an internal
// uuid string. Returns the canonical uuid or "" if not found.
func (s *Store) resolvePersonID(ctx context.Context, idOrQID string) (string, error) {
	if idOrQID == "" {
		return "", nil
	}
	var id string
	err := s.db.QueryRowContext(ctx, `
		SELECT id::VARCHAR FROM person
		WHERE id::VARCHAR = ? OR wikidata_qid = ?
		LIMIT 1
	`, idOrQID, idOrQID).Scan(&id)
	if err == sql.ErrNoRows {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	return id, nil
}

// InsertEvents writes a batch in a single transaction. Invalid events in the
// batch are skipped (the rest still commit). Returns inserted count.
func (s *Store) InsertEvents(
	ctx context.Context,
	events []EventInput,
	userAgent string,
	country string,
) (int, error) {
	if len(events) == 0 {
		return 0, nil
	}
	uaHash := hashUA(userAgent)
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return 0, fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback()

	stmt, err := tx.PrepareContext(ctx, `
		INSERT INTO event (id, event_type, person_id, query, session_id,
		                   referrer, user_agent_hash, country)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)
	`)
	if err != nil {
		return 0, fmt.Errorf("prepare: %w", err)
	}
	defer stmt.Close()

	inserted := 0
	for i := range events {
		ev := &events[i]
		if err := ev.IsValid(); err != nil {
			// Skip invalid; don't abort the batch.
			continue
		}
		eventID := uuid.New().String()
		var personUUID *string
		if ev.PersonID != nil {
			canonical, err := s.resolvePersonID(ctx, *ev.PersonID)
			if err == nil && canonical != "" {
				personUUID = &canonical
			}
		}
		if _, err := stmt.ExecContext(ctx,
			eventID, ev.EventType, personUUID, ev.Query,
			ev.SessionID, ev.Referrer, uaHash, country,
		); err != nil {
			return inserted, fmt.Errorf("insert: %w", err)
		}
		inserted++
	}
	if err := tx.Commit(); err != nil {
		return inserted, fmt.Errorf("commit: %w", err)
	}
	return inserted, nil
}

// ─────────── Trending (public) ───────────

type TrendingItem struct {
	ID          string  `json:"id"`
	WikidataQID *string `json:"wikidata_qid,omitempty"`
	Name        string  `json:"name"`
	Score       float64 `json:"score"`
	Views       int     `json:"views"`
	AvatarURL   *string `json:"avatar_url,omitempty"`
}

// GetTrending returns top-N popular persons within a recent time window.
// Reads directly from `event` (not person_popularity) until the refresh job
// is wired up; window is in days.
func (s *Store) GetTrending(ctx context.Context, windowDays, limit int) ([]TrendingItem, error) {
	if limit <= 0 || limit > 100 {
		limit = 10
	}
	if windowDays <= 0 || windowDays > 90 {
		windowDays = 7
	}
	// Same Q-only guard as GetTree/GetPersonDetail — trending list on the
	// landing should never surface "Q123456" placeholders.
	rows, err := s.db.QueryContext(ctx, `
		WITH counts AS (
			SELECT person_id,
			       COUNT(*) FILTER (WHERE event_type = 'page_view')   AS views,
			       COUNT(*) FILTER (WHERE event_type = 'modal_open')  AS modals,
			       COUNT(*) FILTER (WHERE event_type = 'tree_expand') AS expands,
			       COUNT(*) FILTER (WHERE event_type = 'external_click') AS exits
			FROM event
			WHERE person_id IS NOT NULL
			  AND created_at >= now() - (? * INTERVAL 1 DAY)
			GROUP BY person_id
		)
		SELECT p.id::VARCHAR, p.wikidata_qid, p.birth_name,
		       (c.views + 2*c.modals + 3*c.expands + 5*c.exits) AS score,
		       c.views,
		       p.avatar_url
		FROM counts c
		JOIN person p ON p.id = c.person_id
		WHERE p.birth_name IS NOT NULL AND p.birth_name != ''
		  AND NOT regexp_matches(p.birth_name, '^Q[0-9]+$')
		ORDER BY score DESC
		LIMIT ?
	`, windowDays, limit)
	if err != nil {
		return nil, fmt.Errorf("trending query: %w", err)
	}
	defer rows.Close()

	out := []TrendingItem{}
	for rows.Next() {
		var item TrendingItem
		var qid, avatar sql.NullString
		var score sql.NullFloat64
		var views sql.NullInt64
		if err := rows.Scan(&item.ID, &qid, &item.Name, &score, &views, &avatar); err != nil {
			return nil, fmt.Errorf("scan trending: %w", err)
		}
		if qid.Valid {
			v := qid.String
			item.WikidataQID = &v
		}
		if avatar.Valid && avatar.String != "" {
			v := avatar.String
			item.AvatarURL = &v
		}
		if score.Valid {
			item.Score = score.Float64
		}
		if views.Valid {
			item.Views = int(views.Int64)
		}
		out = append(out, item)
	}
	return out, rows.Err()
}

// ─────────── Admin: priority enrichment queue ───────────

type EnrichmentItem struct {
	ID                string  `json:"id"`
	WikidataQID       *string `json:"wikidata_qid,omitempty"`
	Name              string  `json:"name"`
	WikipediaVIURL    *string `json:"wikipedia_vi_url,omitempty"`
	Score             float64 `json:"score"`
	Views30d          int     `json:"views_30d"`
	HasBio            bool    `json:"has_bio"`
}

// GetPriorityEnrichment returns persons sorted by popularity score; useful
// for picking who to enrich next. `missingBioOnly` filters to persons without
// `bio_short` so enrichment effort goes where it's needed.
//
// Reads from `event` directly (not person_popularity) until refresh job lands.
func (s *Store) GetPriorityEnrichment(
	ctx context.Context,
	limit int,
	missingBioOnly bool,
) ([]EnrichmentItem, error) {
	if limit <= 0 || limit > 500 {
		limit = 100
	}
	bioFilter := ""
	if missingBioOnly {
		bioFilter = "AND (p.bio_short IS NULL OR p.bio_short = '')"
	}
	q := fmt.Sprintf(`
		WITH counts AS (
			SELECT person_id,
			       COUNT(*) FILTER (WHERE event_type = 'page_view')   AS views,
			       COUNT(*) FILTER (WHERE event_type = 'modal_open')  AS modals,
			       COUNT(*) FILTER (WHERE event_type = 'tree_expand') AS expands,
			       COUNT(*) FILTER (WHERE event_type = 'external_click') AS exits
			FROM event
			WHERE person_id IS NOT NULL
			  AND created_at >= now() - INTERVAL 30 DAY
			GROUP BY person_id
		)
		SELECT p.id::VARCHAR, p.wikidata_qid, p.birth_name, p.wikipedia_vi_url,
		       (c.views + 2*c.modals + 3*c.expands + 5*c.exits) AS score,
		       c.views,
		       (p.bio_short IS NOT NULL AND p.bio_short != '') AS has_bio
		FROM counts c
		JOIN person p ON p.id = c.person_id
		WHERE 1=1 %s
		ORDER BY score DESC
		LIMIT ?
	`, bioFilter)

	rows, err := s.db.QueryContext(ctx, q, limit)
	if err != nil {
		return nil, fmt.Errorf("priority query: %w", err)
	}
	defer rows.Close()

	out := []EnrichmentItem{}
	for rows.Next() {
		var item EnrichmentItem
		var qid, wikiURL sql.NullString
		var score sql.NullFloat64
		var views sql.NullInt64
		if err := rows.Scan(&item.ID, &qid, &item.Name, &wikiURL, &score, &views, &item.HasBio); err != nil {
			return nil, fmt.Errorf("scan priority: %w", err)
		}
		if qid.Valid {
			v := qid.String
			item.WikidataQID = &v
		}
		if wikiURL.Valid && wikiURL.String != "" {
			v := wikiURL.String
			item.WikipediaVIURL = &v
		}
		if score.Valid {
			item.Score = score.Float64
		}
		if views.Valid {
			item.Views30d = int(views.Int64)
		}
		out = append(out, item)
	}
	return out, rows.Err()
}

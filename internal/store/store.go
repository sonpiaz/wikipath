package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"

	_ "github.com/marcboeker/go-duckdb/v2"
)

// Store wraps a read-only DuckDB connection.
type Store struct {
	db *sql.DB
}

func Open(path string) (*Store, error) {
	db, err := sql.Open("duckdb", path+"?access_mode=read_only")
	if err != nil {
		return nil, fmt.Errorf("open duckdb: %w", err)
	}
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("ping duckdb: %w", err)
	}
	db.SetMaxOpenConns(8)
	return &Store{db: db}, nil
}

func (s *Store) Close() error { return s.db.Close() }

// ─────────── Search ───────────

type Suggestion struct {
	ID            string   `json:"id"`
	WikidataQID   *string  `json:"wikidata_qid,omitempty"`
	Name          string   `json:"name"`
	BirthYear     *int     `json:"birth_year,omitempty"`
	DeathYear     *int     `json:"death_year,omitempty"`
	BirthPlace    *string  `json:"birth_place,omitempty"`
	BioShort      *string  `json:"bio_short,omitempty"`
	Era           string   `json:"era"`
	Dynasty       *string  `json:"dynasty,omitempty"`
	Lineage       *string  `json:"lineage,omitempty"`
	Trust         int      `json:"trust"`
	SourceBadges  []string `json:"source_badges"`
}

type SearchResult struct {
	Verified  []Suggestion `json:"verified"`
	Community []Suggestion `json:"community"`
	Q         string       `json:"q"`
}

// vnNormalize: lowercase + strip diacritics + đ→d
const normalizeExpr = "LOWER(REPLACE(REPLACE(strip_accents(birth_name), 'đ', 'd'), 'Đ', 'd'))"

func vnNormalize(s string) string {
	// Mirror SQL's normalization on the input side.
	s = strings.ToLower(s)
	s = strings.ReplaceAll(s, "đ", "d")
	s = strings.ReplaceAll(s, "Đ", "d")
	return stripDiacritics(s)
}

func stripDiacritics(s string) string {
	// Minimal manual mapping for common Vietnamese characters.
	// (DuckDB's strip_accents handles the SQL side; we just need parity here
	// for reasonable matching of partial query terms.)
	repl := []struct{ a, b string }{
		{"à", "a"}, {"á", "a"}, {"ả", "a"}, {"ã", "a"}, {"ạ", "a"},
		{"ă", "a"}, {"ằ", "a"}, {"ắ", "a"}, {"ẳ", "a"}, {"ẵ", "a"}, {"ặ", "a"},
		{"â", "a"}, {"ầ", "a"}, {"ấ", "a"}, {"ẩ", "a"}, {"ẫ", "a"}, {"ậ", "a"},
		{"è", "e"}, {"é", "e"}, {"ẻ", "e"}, {"ẽ", "e"}, {"ẹ", "e"},
		{"ê", "e"}, {"ề", "e"}, {"ế", "e"}, {"ể", "e"}, {"ễ", "e"}, {"ệ", "e"},
		{"ì", "i"}, {"í", "i"}, {"ỉ", "i"}, {"ĩ", "i"}, {"ị", "i"},
		{"ò", "o"}, {"ó", "o"}, {"ỏ", "o"}, {"õ", "o"}, {"ọ", "o"},
		{"ô", "o"}, {"ồ", "o"}, {"ố", "o"}, {"ổ", "o"}, {"ỗ", "o"}, {"ộ", "o"},
		{"ơ", "o"}, {"ờ", "o"}, {"ớ", "o"}, {"ở", "o"}, {"ỡ", "o"}, {"ợ", "o"},
		{"ù", "u"}, {"ú", "u"}, {"ủ", "u"}, {"ũ", "u"}, {"ụ", "u"},
		{"ư", "u"}, {"ừ", "u"}, {"ứ", "u"}, {"ử", "u"}, {"ữ", "u"}, {"ự", "u"},
		{"ỳ", "y"}, {"ý", "y"}, {"ỷ", "y"}, {"ỹ", "y"}, {"ỵ", "y"},
	}
	for _, r := range repl {
		s = strings.ReplaceAll(s, r.a, r.b)
	}
	return s
}

func (s *Store) Search(ctx context.Context, q string, limit int) (*SearchResult, error) {
	if limit <= 0 || limit > 200 {
		limit = 50
	}
	qn := vnNormalize(strings.TrimSpace(q))

	args := []any{}
	where := "1=1"
	if qn != "" {
		where = fmt.Sprintf("%s LIKE '%%' || ? || '%%'", normalizeExpr)
		args = append(args, qn)
	}
	args = append(args, limit)

	sqlQ := fmt.Sprintf(`
		SELECT id::VARCHAR, wikidata_qid, birth_name,
		       birth_date_y, death_date_y,
		       birth_place, bio_short,
		       era, dynasty, current_family_name, lineage_branch,
		       trust_score, primary_source
		FROM person
		WHERE %s
		ORDER BY
		    (wikidata_qid IS NOT NULL) DESC,
		    trust_score DESC,
		    birth_date_y NULLS LAST,
		    birth_name
		LIMIT ?
	`, where)

	rows, err := s.db.QueryContext(ctx, sqlQ, args...)
	if err != nil {
		return nil, fmt.Errorf("search query: %w", err)
	}
	defer rows.Close()

	res := &SearchResult{Q: q, Verified: []Suggestion{}, Community: []Suggestion{}}
	for rows.Next() {
		var sug Suggestion
		var qid, bp, bio, dyn, family, branch, src sql.NullString
		var by, dy, trust sql.NullInt64
		if err := rows.Scan(
			&sug.ID, &qid, &sug.Name,
			&by, &dy,
			&bp, &bio,
			&sug.Era, &dyn, &family, &branch,
			&trust, &src,
		); err != nil {
			return nil, fmt.Errorf("scan: %w", err)
		}
		if qid.Valid {
			v := qid.String
			sug.WikidataQID = &v
			sug.SourceBadges = append(sug.SourceBadges, "wikidata")
		}
		if by.Valid {
			v := int(by.Int64)
			sug.BirthYear = &v
		}
		if dy.Valid {
			v := int(dy.Int64)
			sug.DeathYear = &v
		}
		if bp.Valid && bp.String != "" {
			v := bp.String
			sug.BirthPlace = &v
		}
		if bio.Valid && bio.String != "" {
			v := bio.String
			sug.BioShort = &v
		}
		if dyn.Valid && dyn.String != "" {
			v := dyn.String
			sug.Dynasty = &v
		}
		if family.Valid && family.String != "" {
			lineage := family.String
			if branch.Valid && branch.String != "" {
				lineage = lineage + " · " + branch.String
			}
			sug.Lineage = &lineage
		}
		if trust.Valid {
			sug.Trust = int(trust.Int64)
		}
		if src.Valid && (strings.HasPrefix(src.String, "https://vi.wikipedia") || src.String == "wikipedia_vi") {
			sug.SourceBadges = append(sug.SourceBadges, "wikipedia")
		}
		// 3-tier grouping
		if sug.WikidataQID != nil || hasBadge(sug.SourceBadges, "wikipedia") {
			res.Verified = append(res.Verified, sug)
		} else {
			res.Community = append(res.Community, sug)
		}
	}
	return res, rows.Err()
}

func hasBadge(badges []string, b string) bool {
	for _, x := range badges {
		if x == b {
			return true
		}
	}
	return false
}

// ─────────── Tree ───────────

type TreeNode struct {
	ID          string  `json:"id"`
	Name        string  `json:"name"`
	WikidataQID *string `json:"wikidata_qid,omitempty"`
	BirthYear   *int    `json:"birth_year,omitempty"`
	DeathYear   *int    `json:"death_year,omitempty"`
	Era         string  `json:"era"`
	Dynasty     *string `json:"dynasty,omitempty"`
	Gender      string  `json:"gender"`
}

type TreeEdge struct {
	From string `json:"from"`
	To   string `json:"to"`
	Kind string `json:"kind"`
	Rank *int   `json:"rank,omitempty"`
}

type Tree struct {
	Ego      string     `json:"ego"`
	Nodes    []TreeNode `json:"nodes"`
	Edges    []TreeEdge `json:"edges"`
}

// GetTree returns ego + ancestors (up to upN) + descendants (up to downN) +
// ego's spouses + ego's siblings.
func (s *Store) GetTree(ctx context.Context, idOrQID string, upN, downN int) (*Tree, error) {
	if upN < 0 || upN > 8 {
		upN = 4
	}
	if downN < 0 || downN > 8 {
		downN = 3
	}

	// Resolve ego id
	var egoID, egoName string
	row := s.db.QueryRowContext(ctx, `
		SELECT id::VARCHAR, birth_name FROM person
		WHERE id::VARCHAR = ? OR wikidata_qid = ?
		LIMIT 1
	`, idOrQID, idOrQID)
	if err := row.Scan(&egoID, &egoName); err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("person not found: %s", idOrQID)
		}
		return nil, fmt.Errorf("resolve ego: %w", err)
	}

	tree := &Tree{Ego: egoID, Nodes: []TreeNode{}, Edges: []TreeEdge{}}
	seenNode := map[string]bool{}
	seenEdge := map[string]bool{}

	// Collect all ids of interest in 4 BFS phases:
	// 1. ego itself
	// 2. ancestors via parent_father / parent_mother (up to upN)
	// 3. descendants via inverse parent_* + child_* (up to downN)
	// 4. ego's spouses + siblings (1 hop only)

	// Phase 1: ego
	if err := s.loadAndAddNode(ctx, egoID, tree, seenNode); err != nil {
		return nil, err
	}

	// Phase 2: ancestors
	if upN > 0 {
		ancestors, ancestorEdges, err := s.collectAncestors(ctx, egoID, upN)
		if err != nil {
			return nil, fmt.Errorf("ancestors: %w", err)
		}
		for _, id := range ancestors {
			if err := s.loadAndAddNode(ctx, id, tree, seenNode); err != nil {
				return nil, err
			}
		}
		for _, e := range ancestorEdges {
			addEdge(tree, seenEdge, e)
		}
	}

	// Phase 3: descendants
	if downN > 0 {
		desc, descEdges, err := s.collectDescendants(ctx, egoID, downN)
		if err != nil {
			return nil, fmt.Errorf("descendants: %w", err)
		}
		for _, id := range desc {
			if err := s.loadAndAddNode(ctx, id, tree, seenNode); err != nil {
				return nil, err
			}
		}
		for _, e := range descEdges {
			addEdge(tree, seenEdge, e)
		}
	}

	// Phase 4: spouses + siblings of ego
	spouseEdges, err := s.collectSpouses(ctx, egoID)
	if err != nil {
		return nil, fmt.Errorf("spouses: %w", err)
	}
	for _, e := range spouseEdges {
		other := e.To
		if e.From != egoID {
			other = e.From
		}
		if err := s.loadAndAddNode(ctx, other, tree, seenNode); err != nil {
			return nil, err
		}
		addEdge(tree, seenEdge, e)
	}

	siblingEdges, err := s.collectSiblings(ctx, egoID)
	if err != nil {
		return nil, fmt.Errorf("siblings: %w", err)
	}
	for _, e := range siblingEdges {
		other := e.To
		if e.From != egoID {
			other = e.From
		}
		if err := s.loadAndAddNode(ctx, other, tree, seenNode); err != nil {
			return nil, err
		}
		addEdge(tree, seenEdge, e)
	}

	return tree, nil
}

func addEdge(t *Tree, seen map[string]bool, e TreeEdge) {
	key := e.From + "|" + e.Kind + "|" + e.To
	if seen[key] {
		return
	}
	seen[key] = true
	t.Edges = append(t.Edges, e)
}

func (s *Store) loadAndAddNode(ctx context.Context, id string, t *Tree, seen map[string]bool) error {
	if seen[id] {
		return nil
	}
	row := s.db.QueryRowContext(ctx, `
		SELECT id::VARCHAR, birth_name, wikidata_qid,
		       birth_date_y, death_date_y, era, dynasty, gender
		FROM person WHERE id::VARCHAR = ?
	`, id)
	var n TreeNode
	var qid, dyn sql.NullString
	var by, dy sql.NullInt64
	if err := row.Scan(&n.ID, &n.Name, &qid, &by, &dy, &n.Era, &dyn, &n.Gender); err != nil {
		if err == sql.ErrNoRows {
			return nil
		}
		return fmt.Errorf("load node %s: %w", id, err)
	}
	if qid.Valid {
		v := qid.String
		n.WikidataQID = &v
	}
	if by.Valid {
		v := int(by.Int64)
		n.BirthYear = &v
	}
	if dy.Valid {
		v := int(dy.Int64)
		n.DeathYear = &v
	}
	if dyn.Valid {
		v := dyn.String
		n.Dynasty = &v
	}
	t.Nodes = append(t.Nodes, n)
	seen[id] = true
	return nil
}

func (s *Store) collectAncestors(ctx context.Context, egoID string, depth int) ([]string, []TreeEdge, error) {
	rows, err := s.db.QueryContext(ctx, `
		WITH RECURSIVE up AS (
			SELECT id::VARCHAR AS id, 0 AS depth FROM person WHERE id::VARCHAR = ?
			UNION ALL
			SELECT par.id::VARCHAR, up.depth + 1
			FROM up
			JOIN v_parents vp ON vp.person_id::VARCHAR = up.id
			JOIN person par ON par.id = vp.parent_id
			WHERE up.depth < ?
		)
		SELECT DISTINCT u.id, vp.parent_id::VARCHAR, vp.parent_kind
		FROM up u
		LEFT JOIN v_parents vp ON vp.person_id::VARCHAR = u.id
		WHERE u.depth < ?
	`, egoID, depth, depth)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()
	idSet := map[string]bool{}
	edges := []TreeEdge{}
	for rows.Next() {
		var childID, parentID, parentKind sql.NullString
		if err := rows.Scan(&childID, &parentID, &parentKind); err != nil {
			return nil, nil, err
		}
		if childID.Valid {
			idSet[childID.String] = true
		}
		if parentID.Valid {
			idSet[parentID.String] = true
			kind := "parent_father"
			if parentKind.Valid && parentKind.String == "mother" {
				kind = "parent_mother"
			}
			edges = append(edges, TreeEdge{
				From: childID.String, To: parentID.String, Kind: kind,
			})
		}
	}
	ids := make([]string, 0, len(idSet))
	for id := range idSet {
		if id != egoID {
			ids = append(ids, id)
		}
	}
	return ids, edges, rows.Err()
}

func (s *Store) collectDescendants(ctx context.Context, egoID string, depth int) ([]string, []TreeEdge, error) {
	rows, err := s.db.QueryContext(ctx, `
		WITH RECURSIVE down AS (
			SELECT id::VARCHAR AS id, 0 AS depth FROM person WHERE id::VARCHAR = ?
			UNION ALL
			SELECT ch.child_id::VARCHAR, down.depth + 1
			FROM down
			JOIN v_children ch ON ch.person_id::VARCHAR = down.id
			WHERE down.depth < ?
		)
		SELECT DISTINCT d.id, vc.child_id::VARCHAR, vc.child_kind
		FROM down d
		LEFT JOIN v_children vc ON vc.person_id::VARCHAR = d.id
		WHERE d.depth < ?
	`, egoID, depth, depth)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()
	idSet := map[string]bool{}
	edges := []TreeEdge{}
	for rows.Next() {
		var parentID, childID, childKind sql.NullString
		if err := rows.Scan(&parentID, &childID, &childKind); err != nil {
			return nil, nil, err
		}
		if parentID.Valid {
			idSet[parentID.String] = true
		}
		if childID.Valid {
			idSet[childID.String] = true
			kind := "parent_father"
			if childKind.Valid && childKind.String != "biological" {
				kind = "child_" + childKind.String
			}
			edges = append(edges, TreeEdge{
				From: childID.String, To: parentID.String, Kind: kind,
			})
		}
	}
	ids := make([]string, 0, len(idSet))
	for id := range idSet {
		if id != egoID {
			ids = append(ids, id)
		}
	}
	return ids, edges, rows.Err()
}

func (s *Store) collectSpouses(ctx context.Context, egoID string) ([]TreeEdge, error) {
	rows, err := s.db.QueryContext(ctx, `
		SELECT vs.person_id::VARCHAR, vs.spouse_id::VARCHAR, vs.spouse_kind, vs.rank
		FROM v_spouses vs
		WHERE vs.person_id::VARCHAR = ?
	`, egoID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	edges := []TreeEdge{}
	for rows.Next() {
		var fromID, toID, kind sql.NullString
		var rank sql.NullInt64
		if err := rows.Scan(&fromID, &toID, &kind, &rank); err != nil {
			return nil, err
		}
		e := TreeEdge{From: fromID.String, To: toID.String, Kind: kind.String}
		if rank.Valid {
			r := int(rank.Int64)
			e.Rank = &r
		}
		edges = append(edges, e)
	}
	return edges, rows.Err()
}

func (s *Store) collectSiblings(ctx context.Context, egoID string) ([]TreeEdge, error) {
	rows, err := s.db.QueryContext(ctx, `
		SELECT vs.person_id::VARCHAR, vs.sibling_id::VARCHAR, vs.sibling_kind
		FROM v_siblings vs
		WHERE vs.person_id::VARCHAR = ?
	`, egoID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	edges := []TreeEdge{}
	for rows.Next() {
		var fromID, toID, kind sql.NullString
		if err := rows.Scan(&fromID, &toID, &kind); err != nil {
			return nil, err
		}
		edges = append(edges, TreeEdge{From: fromID.String, To: toID.String, Kind: kind.String})
	}
	return edges, rows.Err()
}

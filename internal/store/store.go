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
	// Read-write so the API can also persist analytics events (F8). Python
	// batch jobs (enrichment, image import) require the API to be stopped
	// — same constraint as a read-only handle since DuckDB serializes file
	// locks across processes regardless of access mode.
	db, err := sql.Open("duckdb", path+"?access_mode=read_write")
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
	AvatarURL     *string  `json:"avatar_url,omitempty"`
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

// vnNormalize: lowercase + strip diacritics + đ→d.
// Apply to a column expression like `birth_name` or `n.name`.
func normalizeExpr(col string) string {
	return fmt.Sprintf("LOWER(REPLACE(REPLACE(strip_accents(%s), 'đ', 'd'), 'Đ', 'd'))", col)
}

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

	var sqlQ string
	args := []any{}
	if qn == "" {
		// No query: just list everyone, ordered by quality.
		// Hide records where birth_name is empty/null — those records exist
		// only as a Wikidata QID and surface to users as "Q12345" noise.
		sqlQ = `
			SELECT id::VARCHAR, wikidata_qid, birth_name,
			       birth_date_y, death_date_y,
			       birth_place, bio_short, avatar_url,
			       era, dynasty, current_family_name, lineage_branch,
			       trust_score, primary_source
			FROM person
			WHERE birth_name IS NOT NULL AND birth_name != '' AND NOT regexp_matches(birth_name, '^Q?[0-9]+$')
			ORDER BY
			    (wikidata_qid IS NOT NULL) DESC,
			    trust_score DESC,
			    birth_date_y NULLS LAST,
			    birth_name
			LIMIT ?
		`
		args = append(args, limit)
	} else {
		// Match against birth_name OR any alt name. UNION dedupes by person id.
		sqlQ = fmt.Sprintf(`
			WITH matches AS (
				SELECT id FROM person WHERE %s LIKE '%%' || ? || '%%'
				UNION
				SELECT n.person_id AS id FROM name n WHERE %s LIKE '%%' || ? || '%%'
			)
			SELECT p.id::VARCHAR, p.wikidata_qid, p.birth_name,
			       p.birth_date_y, p.death_date_y,
			       p.birth_place, p.bio_short, p.avatar_url,
			       p.era, p.dynasty, p.current_family_name, p.lineage_branch,
			       p.trust_score, p.primary_source
			FROM person p
			JOIN matches m ON m.id = p.id
			ORDER BY
			    (p.wikidata_qid IS NOT NULL) DESC,
			    p.trust_score DESC,
			    p.birth_date_y NULLS LAST,
			    p.birth_name
			LIMIT ?
		`, normalizeExpr("birth_name"), normalizeExpr("n.name"))
		args = append(args, qn, qn, limit)
	}

	rows, err := s.db.QueryContext(ctx, sqlQ, args...)
	if err != nil {
		return nil, fmt.Errorf("search query: %w", err)
	}
	defer rows.Close()

	res := &SearchResult{Q: q, Verified: []Suggestion{}, Community: []Suggestion{}}
	for rows.Next() {
		sug := Suggestion{SourceBadges: []string{}}
		var qid, bp, bio, avatar, dyn, family, branch, src sql.NullString
		var by, dy, trust sql.NullInt64
		if err := rows.Scan(
			&sug.ID, &qid, &sug.Name,
			&by, &dy,
			&bp, &bio, &avatar,
			&sug.Era, &dyn, &family, &branch,
			&trust, &src,
		); err != nil {
			return nil, fmt.Errorf("scan: %w", err)
		}
		if avatar.Valid && avatar.String != "" {
			v := avatar.String
			sug.AvatarURL = &v
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
	AvatarURL   *string `json:"avatar_url,omitempty"`
	BioShort    *string `json:"bio_short,omitempty"`
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

// PersonDetail is the rich payload for the click-to-preview modal.
type PersonDetail struct {
	ID              string   `json:"id"`
	WikidataQID     *string  `json:"wikidata_qid,omitempty"`
	WikipediaVIURL  *string  `json:"wikipedia_vi_url,omitempty"`
	Name            string   `json:"name"`
	BirthYear       *int     `json:"birth_year,omitempty"`
	BirthMonth      *int     `json:"birth_month,omitempty"`
	BirthDay        *int     `json:"birth_day,omitempty"`
	DeathYear       *int     `json:"death_year,omitempty"`
	DeathMonth      *int     `json:"death_month,omitempty"`
	DeathDay        *int     `json:"death_day,omitempty"`
	BirthPlace      *string  `json:"birth_place,omitempty"`
	DeathPlace      *string  `json:"death_place,omitempty"`
	BioShort        *string  `json:"bio_short,omitempty"`
	BioFull         *string  `json:"bio_full,omitempty"`
	AvatarURL       *string  `json:"avatar_url,omitempty"`
	Era             string   `json:"era"`
	Dynasty         *string  `json:"dynasty,omitempty"`
	FamilyName      *string  `json:"family_name,omitempty"`
	LineageBranch   *string  `json:"lineage_branch,omitempty"`
	Gender          string   `json:"gender"`
	Historicity     string   `json:"historicity"`
	IsLiving        bool     `json:"is_living"`
	TrustScore      int      `json:"trust_score"`
	PrimarySource   *string  `json:"primary_source,omitempty"`
	SourceBadges    []string `json:"source_badges"`
	AltNames        []AltName `json:"alt_names"`
	// Counts for quick stats
	ParentCount     int `json:"parent_count"`
	SpouseCount     int `json:"spouse_count"`
	ChildCount      int `json:"child_count"`
	SiblingCount    int `json:"sibling_count"`
	AncestorCount   int `json:"ancestor_count_4_gen"`
	DescendantCount int `json:"descendant_count_3_gen"`
}

type AltName struct {
	Name string `json:"name"`
	Kind string `json:"kind"`
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

	// Resolve ego id. Reject Q-only fallback records (birth_name empty) — the
	// page would render with a QID heading, no relations, no bio. Better to
	// 404 and let the user search by name.
	var egoID, egoName string
	row := s.db.QueryRowContext(ctx, `
		SELECT id::VARCHAR, birth_name FROM person
		WHERE (id::VARCHAR = ? OR wikidata_qid = ?)
		  AND birth_name IS NOT NULL AND birth_name != '' AND NOT regexp_matches(birth_name, '^Q?[0-9]+$')
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

	// Drop edges referencing nodes that loadAndAddNode skipped (Q-only
	// records without a birth_name). The collect* helpers query the relation
	// table directly and don't know which IDs got filtered, so prune here.
	named := make(map[string]bool, len(tree.Nodes))
	for _, n := range tree.Nodes {
		named[n.ID] = true
	}
	kept := tree.Edges[:0]
	for _, e := range tree.Edges {
		if named[e.From] && named[e.To] {
			kept = append(kept, e)
		}
	}
	tree.Edges = kept

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
		       birth_date_y, death_date_y, era, dynasty, gender, avatar_url, bio_short
		FROM person
		WHERE id::VARCHAR = ?
		  AND birth_name IS NOT NULL AND birth_name != '' AND NOT regexp_matches(birth_name, '^Q?[0-9]+$')
	`, id)
	var n TreeNode
	var qid, dyn, avatar, bio sql.NullString
	var by, dy sql.NullInt64
	if err := row.Scan(&n.ID, &n.Name, &qid, &by, &dy, &n.Era, &dyn, &n.Gender, &avatar, &bio); err != nil {
		if err == sql.ErrNoRows {
			// Person exists in DB but has no name yet (Wikidata structural
			// import without enrichment). Mark as seen so we don't re-query,
			// but don't add the unnamed node to the tree.
			seen[id] = true
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
	if avatar.Valid && avatar.String != "" {
		v := avatar.String
		n.AvatarURL = &v
	}
	if bio.Valid && bio.String != "" {
		v := bio.String
		n.BioShort = &v
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

func (s *Store) GetPersonDetail(ctx context.Context, idOrQID string) (*PersonDetail, error) {
	// Same Q-only guard as GetTree: refuse records without a birth_name.
	row := s.db.QueryRowContext(ctx, `
		SELECT id::VARCHAR, wikidata_qid, wikipedia_vi_url, birth_name,
		       birth_date_y, birth_date_m, birth_date_d,
		       death_date_y, death_date_m, death_date_d,
		       birth_place, death_place,
		       bio_short, bio_full, avatar_url,
		       era, dynasty, current_family_name, lineage_branch,
		       gender, historicity, is_living,
		       trust_score, primary_source
		FROM person
		WHERE (id::VARCHAR = ? OR wikidata_qid = ?)
		  AND birth_name IS NOT NULL AND birth_name != '' AND NOT regexp_matches(birth_name, '^Q?[0-9]+$')
		LIMIT 1
	`, idOrQID, idOrQID)

	var d PersonDetail
	d.SourceBadges = []string{}
	d.AltNames = []AltName{}
	var qid, wikiURL, bp, dp, bio, bioFull, avatar, dyn, family, branch, src sql.NullString
	var by, bm, bd, dy, dm, dd, trust sql.NullInt64
	if err := row.Scan(
		&d.ID, &qid, &wikiURL, &d.Name,
		&by, &bm, &bd,
		&dy, &dm, &dd,
		&bp, &dp,
		&bio, &bioFull, &avatar,
		&d.Era, &dyn, &family, &branch,
		&d.Gender, &d.Historicity, &d.IsLiving,
		&trust, &src,
	); err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("person not found: %s", idOrQID)
		}
		return nil, fmt.Errorf("scan detail: %w", err)
	}

	assignNullStr := func(out **string, v sql.NullString) {
		if v.Valid && v.String != "" {
			s := v.String
			*out = &s
		}
	}
	assignNullStr(&d.WikidataQID, qid)
	assignNullStr(&d.WikipediaVIURL, wikiURL)
	assignNullStr(&d.BirthPlace, bp)
	assignNullStr(&d.DeathPlace, dp)
	assignNullStr(&d.BioShort, bio)
	assignNullStr(&d.BioFull, bioFull)
	assignNullStr(&d.AvatarURL, avatar)
	assignNullStr(&d.Dynasty, dyn)
	assignNullStr(&d.FamilyName, family)
	assignNullStr(&d.LineageBranch, branch)
	assignNullStr(&d.PrimarySource, src)

	assignNullInt := func(out **int, v sql.NullInt64) {
		if v.Valid {
			n := int(v.Int64)
			*out = &n
		}
	}
	assignNullInt(&d.BirthYear, by)
	assignNullInt(&d.BirthMonth, bm)
	assignNullInt(&d.BirthDay, bd)
	assignNullInt(&d.DeathYear, dy)
	assignNullInt(&d.DeathMonth, dm)
	assignNullInt(&d.DeathDay, dd)
	if trust.Valid {
		d.TrustScore = int(trust.Int64)
	}

	if d.WikidataQID != nil {
		d.SourceBadges = append(d.SourceBadges, "wikidata")
	}
	if d.PrimarySource != nil &&
		(strings.HasPrefix(*d.PrimarySource, "https://vi.wikipedia") ||
			*d.PrimarySource == "wikipedia_vi") {
		d.SourceBadges = append(d.SourceBadges, "wikipedia")
	}

	// Alt names
	nameRows, err := s.db.QueryContext(ctx,
		`SELECT name, kind FROM name WHERE person_id::VARCHAR = ? ORDER BY kind`,
		d.ID)
	if err != nil {
		return nil, fmt.Errorf("alt names: %w", err)
	}
	defer nameRows.Close()
	for nameRows.Next() {
		var an AltName
		if err := nameRows.Scan(&an.Name, &an.Kind); err != nil {
			return nil, err
		}
		if an.Name == d.Name {
			continue
		}
		d.AltNames = append(d.AltNames, an)
	}

	// Counts: 1-hop direct relations
	row1 := s.db.QueryRowContext(ctx, `
		SELECT
		    SUM(CASE WHEN kind LIKE 'parent_%' AND from_person_id::VARCHAR = ? THEN 1 ELSE 0 END) AS parents,
		    SUM(CASE WHEN (kind LIKE 'parent_%' AND to_person_id::VARCHAR = ?)
		             OR  (kind LIKE 'child_%'  AND from_person_id::VARCHAR = ?) THEN 1 ELSE 0 END) AS children,
		    SUM(CASE WHEN kind IN ('spouse','concubine')
		             AND (from_person_id::VARCHAR = ? OR to_person_id::VARCHAR = ?) THEN 1 ELSE 0 END) AS spouses,
		    SUM(CASE WHEN kind LIKE 'sibling_%'
		             AND (from_person_id::VARCHAR = ? OR to_person_id::VARCHAR = ?) THEN 1 ELSE 0 END) AS siblings
		FROM relation
	`, d.ID, d.ID, d.ID, d.ID, d.ID, d.ID, d.ID)
	var pCount, cCount, sCount, sibCount sql.NullInt64
	if err := row1.Scan(&pCount, &cCount, &sCount, &sibCount); err == nil {
		d.ParentCount = int(pCount.Int64)
		d.ChildCount = int(cCount.Int64)
		d.SpouseCount = int(sCount.Int64)
		d.SiblingCount = int(sibCount.Int64)
	}

	// Recursive ancestor + descendant counts up to 4/3 generations
	if r := s.db.QueryRowContext(ctx, `
		WITH RECURSIVE up AS (
			SELECT id::VARCHAR AS id, 0 AS depth FROM person WHERE id::VARCHAR = ?
			UNION ALL
			SELECT par.id::VARCHAR, up.depth + 1
			FROM up
			JOIN v_parents vp ON vp.person_id::VARCHAR = up.id
			JOIN person par ON par.id = vp.parent_id
			WHERE up.depth < 4
		)
		SELECT COUNT(*) - 1 FROM up
	`, d.ID); r != nil {
		var n sql.NullInt64
		_ = r.Scan(&n)
		d.AncestorCount = int(n.Int64)
	}
	if r := s.db.QueryRowContext(ctx, `
		WITH RECURSIVE down AS (
			SELECT id::VARCHAR AS id, 0 AS depth FROM person WHERE id::VARCHAR = ?
			UNION ALL
			SELECT ch.child_id::VARCHAR, down.depth + 1
			FROM down
			JOIN v_children ch ON ch.person_id::VARCHAR = down.id
			WHERE down.depth < 3
		)
		SELECT COUNT(DISTINCT id) - 1 FROM down
	`, d.ID); r != nil {
		var n sql.NullInt64
		_ = r.Scan(&n)
		d.DescendantCount = int(n.Int64)
	}

	return &d, nil
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

package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
)

// ─────────── Compare / path (F5) ───────────
//
// Finds the shortest undirected path through the `relation` table between
// two persons. Iterative BFS in Go, batching one neighbor query per level
// so we never exceed `maxDepth` round-trips.

type PathHop struct {
	From     string  `json:"from"`
	To       string  `json:"to"`
	Kind     string  `json:"kind"`
	Rank     *int    `json:"rank,omitempty"`
	// Forward = true if the edge in the DB had from=From, to=To.
	// False when we traversed the edge in reverse direction (e.g. ego→parent
	// when the stored edge is parent_father with from=child, to=parent).
	Forward  bool    `json:"forward"`
}

type PathNode struct {
	ID          string  `json:"id"`
	Name        string  `json:"name"`
	WikidataQID *string `json:"wikidata_qid,omitempty"`
	BirthYear   *int    `json:"birth_year,omitempty"`
	DeathYear   *int    `json:"death_year,omitempty"`
	AvatarURL   *string `json:"avatar_url,omitempty"`
}

type Path struct {
	From      PathNode   `json:"from"`
	To        PathNode   `json:"to"`
	Distance  int        `json:"distance"`            // number of hops
	Nodes     []PathNode `json:"nodes"`               // ordered, includes from + to
	Hops      []PathHop  `json:"hops"`                // len = distance
	// CommonAncestor populated when the shortest path goes through a node
	// that is an ancestor of BOTH endpoints (heuristic, see below).
	CommonAncestor *string `json:"common_ancestor,omitempty"`
}

// edgeRef stores one edge as encountered during BFS expansion.
type edgeRef struct {
	from, to string
	kind     string
	rank     *int
	forward  bool // see PathHop.Forward
}

// FindPath returns the shortest undirected path between two persons.
// `maxDepth` caps BFS levels (0 = no limit; recommend 8 for sanity).
func (s *Store) FindPath(
	ctx context.Context,
	fromIDOrQID, toIDOrQID string,
	maxDepth int,
) (*Path, error) {
	if maxDepth <= 0 || maxDepth > 12 {
		maxDepth = 8
	}

	fromID, err := s.resolvePersonID(ctx, fromIDOrQID)
	if err != nil {
		return nil, fmt.Errorf("resolve from: %w", err)
	}
	if fromID == "" {
		return nil, fmt.Errorf("person not found: %s", fromIDOrQID)
	}
	toID, err := s.resolvePersonID(ctx, toIDOrQID)
	if err != nil {
		return nil, fmt.Errorf("resolve to: %w", err)
	}
	if toID == "" {
		return nil, fmt.Errorf("person not found: %s", toIDOrQID)
	}

	// parent map: child node id -> edge that reached it
	parent := map[string]*edgeRef{fromID: nil}
	frontier := []string{fromID}

	for level := 0; level < maxDepth; level++ {
		if len(frontier) == 0 {
			break
		}
		// Stop early if target already discovered
		if _, ok := parent[toID]; ok {
			break
		}

		nextFrontier, err := s.expandFrontier(ctx, frontier, parent)
		if err != nil {
			return nil, fmt.Errorf("expand level %d: %w", level, err)
		}
		frontier = nextFrontier
	}

	if _, ok := parent[toID]; !ok {
		return nil, fmt.Errorf("no path within %d hops", maxDepth)
	}

	// Reconstruct: walk back from toID to fromID using parent map
	var revHops []PathHop
	cur := toID
	for cur != fromID {
		e := parent[cur]
		if e == nil {
			return nil, fmt.Errorf("path reconstruction broken at %s", cur)
		}
		revHops = append(revHops, PathHop{
			From:    e.from,
			To:      e.to,
			Kind:    e.kind,
			Rank:    e.rank,
			Forward: e.forward,
		})
		// Move to the OTHER endpoint of the edge (the one we came from).
		if e.forward {
			cur = e.from
		} else {
			cur = e.to
		}
	}
	// Reverse — we built tail-first.
	hops := make([]PathHop, len(revHops))
	for i, h := range revHops {
		hops[len(revHops)-1-i] = h
	}

	// Collect node ids in path order
	nodeIDs := []string{fromID}
	cur = fromID
	for _, h := range hops {
		// next node is the OTHER endpoint of the hop relative to `cur`
		if h.Forward {
			if h.From == cur {
				cur = h.To
			} else {
				cur = h.From
			}
		} else {
			if h.To == cur {
				cur = h.From
			} else {
				cur = h.To
			}
		}
		nodeIDs = append(nodeIDs, cur)
	}

	// Bulk-load node details for the path
	nodes, err := s.loadNodes(ctx, nodeIDs)
	if err != nil {
		return nil, fmt.Errorf("load path nodes: %w", err)
	}

	path := &Path{
		From:     nodes[0],
		To:       nodes[len(nodes)-1],
		Distance: len(hops),
		Nodes:    nodes,
		Hops:     hops,
	}

	// Common ancestor heuristic: the highest interior node whose hops in and
	// out are both parent_* in opposite directions = it's an ancestor of
	// both endpoints. Skip endpoints themselves.
	for i := 1; i < len(nodes)-1; i++ {
		left := hops[i-1]
		right := hops[i]
		if isParentEdge(left.Kind) && isParentEdge(right.Kind) {
			// left arrived AT this node (the parent of the previous person)
			// right departs FROM this node going DOWN (parent of next person)
			// The direction signs depend on Forward flags — easiest sanity:
			// if both edges have this node on the parent side, it's an ancestor.
			//   parent_* in DB: from=child, to=parent
			//   If left.To == nodes[i].ID then nodes[i] is the parent on left edge.
			//   If right.To == nodes[i].ID then nodes[i] is the parent on right edge.
			isParentOnLeft := left.To == nodes[i].ID
			isParentOnRight := right.To == nodes[i].ID
			if isParentOnLeft && isParentOnRight {
				v := nodes[i].ID
				path.CommonAncestor = &v
				break
			}
		}
	}

	return path, nil
}

func isParentEdge(kind string) bool {
	return kind == "parent_father" || kind == "parent_mother" ||
		strings.HasPrefix(kind, "child_")
}

func (s *Store) expandFrontier(
	ctx context.Context,
	frontier []string,
	parent map[string]*edgeRef,
) ([]string, error) {
	if len(frontier) == 0 {
		return nil, nil
	}
	placeholders := strings.Repeat("?,", len(frontier))
	placeholders = placeholders[:len(placeholders)-1]
	args := make([]any, 0, len(frontier)*2)
	for _, id := range frontier {
		args = append(args, id)
	}
	for _, id := range frontier {
		args = append(args, id)
	}

	q := fmt.Sprintf(`
		SELECT from_person_id::VARCHAR, to_person_id::VARCHAR, kind, rank
		FROM relation
		WHERE from_person_id::VARCHAR IN (%s)
		   OR to_person_id::VARCHAR   IN (%s)
	`, placeholders, placeholders)

	rows, err := s.db.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var next []string
	for rows.Next() {
		var from, to, kind string
		var rank sql.NullInt64
		if err := rows.Scan(&from, &to, &kind, &rank); err != nil {
			return nil, err
		}
		var rankPtr *int
		if rank.Valid {
			r := int(rank.Int64)
			rankPtr = &r
		}
		// Determine which endpoint is in frontier and which is new
		inFrontFrom := contains(frontier, from)
		inFrontTo := contains(frontier, to)
		if inFrontFrom && !inFrontTo {
			if _, seen := parent[to]; !seen {
				parent[to] = &edgeRef{from: from, to: to, kind: kind, rank: rankPtr, forward: true}
				next = append(next, to)
			}
		} else if inFrontTo && !inFrontFrom {
			if _, seen := parent[from]; !seen {
				parent[from] = &edgeRef{from: from, to: to, kind: kind, rank: rankPtr, forward: false}
				next = append(next, from)
			}
		}
		// If both are in frontier, ignore (same-level cycle).
	}
	return next, rows.Err()
}

func contains(xs []string, x string) bool {
	for _, v := range xs {
		if v == x {
			return true
		}
	}
	return false
}

func (s *Store) loadNodes(ctx context.Context, ids []string) ([]PathNode, error) {
	if len(ids) == 0 {
		return nil, nil
	}
	// Bulk fetch — order preserved via map lookup
	placeholders := strings.Repeat("?,", len(ids))
	placeholders = placeholders[:len(placeholders)-1]
	args := make([]any, 0, len(ids))
	for _, id := range ids {
		args = append(args, id)
	}
	q := fmt.Sprintf(`
		SELECT id::VARCHAR, birth_name, wikidata_qid,
		       birth_date_y, death_date_y, avatar_url
		FROM person
		WHERE id::VARCHAR IN (%s)
	`, placeholders)

	rows, err := s.db.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	lookup := map[string]PathNode{}
	for rows.Next() {
		var n PathNode
		var qid, avatar sql.NullString
		var by, dy sql.NullInt64
		if err := rows.Scan(&n.ID, &n.Name, &qid, &by, &dy, &avatar); err != nil {
			return nil, err
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
		if avatar.Valid && avatar.String != "" {
			v := avatar.String
			n.AvatarURL = &v
		}
		lookup[n.ID] = n
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	out := make([]PathNode, 0, len(ids))
	for _, id := range ids {
		if n, ok := lookup[id]; ok {
			out = append(out, n)
		}
	}
	return out, nil
}

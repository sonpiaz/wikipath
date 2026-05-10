package graph

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
)

type Graph map[string][]string

func Load(path string) (Graph, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open graph %s: %w", path, err)
	}
	defer f.Close()
	var g Graph
	if err := json.NewDecoder(f).Decode(&g); err != nil {
		return nil, fmt.Errorf("decode graph: %w", err)
	}
	return g, nil
}

func (g Graph) Names() []string {
	out := make([]string, 0, len(g))
	for k := range g {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

type LevelEvent struct {
	Level int      `json:"level"`
	Nodes []string `json:"nodes"`
}

func BFS(g Graph, start, end string, onLevel func(LevelEvent)) ([]string, error) {
	if _, ok := g[start]; !ok {
		return nil, fmt.Errorf("start %q not in graph", start)
	}
	if _, ok := g[end]; !ok {
		return nil, fmt.Errorf("end %q not in graph", end)
	}
	if start == end {
		return []string{start}, nil
	}

	parent := map[string]string{start: ""}
	frontier := []string{start}
	level := 0

	for len(frontier) > 0 {
		level++
		var next []string
		for _, node := range frontier {
			for _, neighbor := range g[node] {
				if _, seen := parent[neighbor]; seen {
					continue
				}
				parent[neighbor] = node
				if neighbor == end {
					return reconstruct(parent, start, end), nil
				}
				next = append(next, neighbor)
			}
		}
		if onLevel != nil && len(next) > 0 {
			cp := make([]string, len(next))
			copy(cp, next)
			onLevel(LevelEvent{Level: level, Nodes: cp})
		}
		frontier = next
	}
	return nil, fmt.Errorf("no path from %q to %q", start, end)
}

func reconstruct(parent map[string]string, start, end string) []string {
	var path []string
	for node := end; node != ""; node = parent[node] {
		path = append([]string{node}, path...)
		if node == start {
			break
		}
	}
	return path
}

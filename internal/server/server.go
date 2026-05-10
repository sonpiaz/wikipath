package server

import (
	"encoding/json"
	"fmt"
	"io/fs"
	"net/http"
	"strings"

	"github.com/sonpiaz/wikipath/internal/graph"
)

type Server struct {
	graph  graph.Graph
	names  []string
	webFS  fs.FS
}

func New(g graph.Graph, webFS fs.FS) *Server {
	return &Server{graph: g, names: g.Names(), webFS: webFS}
}

func (s *Server) Routes() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/people", s.handlePeople)
	mux.HandleFunc("/api/search", s.handleSearch)
	mux.Handle("/", http.FileServer(http.FS(s.webFS)))
	return mux
}

func (s *Server) handlePeople(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	q := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("q")))
	out := make([]string, 0)
	limit := len(s.names)
	if q != "" {
		limit = 50
	}
	for _, name := range s.names {
		if len(out) >= limit {
			break
		}
		if q == "" || strings.Contains(strings.ToLower(name), q) {
			out = append(out, name)
		}
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(out)
}

func (s *Server) handleSearch(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	from := r.URL.Query().Get("from")
	to := r.URL.Query().Get("to")
	if from == "" || to == "" {
		http.Error(w, "from and to required", http.StatusBadRequest)
		return
	}

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming unsupported", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")

	send := func(event string, data any) {
		buf, err := json.Marshal(data)
		if err != nil {
			return
		}
		fmt.Fprintf(w, "event: %s\ndata: %s\n\n", event, buf)
		flusher.Flush()
	}

	send("hello", map[string]string{"from": from, "to": to})

	path, err := graph.BFS(s.graph, from, to, func(ev graph.LevelEvent) {
		send("level", ev)
	})
	if err != nil {
		send("error", err.Error())
		send("done", map[string]bool{"ok": false})
		return
	}
	send("path", map[string]any{"path": path, "length": len(path)})
	send("done", map[string]bool{"ok": true})
}

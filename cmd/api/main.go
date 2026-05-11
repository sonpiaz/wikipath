package main

import (
	"context"
	"encoding/json"
	"flag"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/sonpiaz/wikipath/internal/store"
)

func main() {
	dbPath := flag.String("db", "wikipath.duckdb", "path to wikipath duckdb file")
	addr := flag.String("addr", ":8080", "listen address")
	flag.Parse()
	if env := os.Getenv("PORT"); env != "" {
		*addr = ":" + env
	}

	st, err := store.Open(*dbPath)
	if err != nil {
		log.Fatalf("open store: %v", err)
	}
	defer st.Close()

	limiter := newSessionLimiter()
	trendCache := newTrendingCache()

	mux := http.NewServeMux()
	mux.HandleFunc("/api/search", handleSearch(st))
	mux.HandleFunc("/api/p/", routeUnderP(st))
	mux.HandleFunc("/api/event", handleEvent(st, limiter))
	mux.HandleFunc("/api/trending", handleTrending(st, trendCache))
	mux.HandleFunc("/api/admin/popularity", handleAdminPopularity(st))
	mux.HandleFunc("/api/path", handlePath(st))
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("ok"))
	})

	srv := &http.Server{
		Addr:              *addr,
		Handler:           withCORS(withLog(mux)),
		ReadHeaderTimeout: 5 * time.Second,
	}
	log.Printf("wikipath api listening on %s", *addr)
	log.Fatal(srv.ListenAndServe())
}

func handleSearch(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		q := r.URL.Query().Get("q")
		limit := 50
		if v := r.URL.Query().Get("limit"); v != "" {
			if n, err := strconv.Atoi(v); err == nil {
				limit = n
			}
		}
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		res, err := st.Search(ctx, q, limit)
		if err != nil {
			log.Printf("search %q: %v", q, err)
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
			return
		}
		writeJSON(w, http.StatusOK, res)
	}
}

// routeUnderP dispatches:
//   GET /api/p/<id>           -> handleTree
//   GET /api/p/<id>/details   -> handleDetail
func routeUnderP(st *store.Store) http.HandlerFunc {
	tree := handleTree(st)
	detail := handleDetail(st)
	return func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path[len("/api/p/"):]
		path = strings.TrimRight(path, "/")
		if strings.HasSuffix(path, "/details") {
			detail(w, r)
			return
		}
		tree(w, r)
	}
}

func handleTree(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		id := strings.TrimRight(r.URL.Path[len("/api/p/"):], "/")
		if id == "" {
			http.Error(w, "id required", http.StatusBadRequest)
			return
		}
		upN := parseIntDefault(r.URL.Query().Get("up"), 4)
		downN := parseIntDefault(r.URL.Query().Get("down"), 3)
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		tree, err := st.GetTree(ctx, id, upN, downN)
		if err != nil {
			log.Printf("tree %q: %v", id, err)
			writeJSON(w, http.StatusNotFound, map[string]string{"error": err.Error()})
			return
		}
		writeJSON(w, http.StatusOK, tree)
	}
}

func handlePath(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		from := r.URL.Query().Get("from")
		to := r.URL.Query().Get("to")
		if from == "" || to == "" {
			http.Error(w, "from + to required", http.StatusBadRequest)
			return
		}
		maxDepth := parseIntDefault(r.URL.Query().Get("max"), 8)
		ctx, cancel := context.WithTimeout(r.Context(), 8*time.Second)
		defer cancel()
		p, err := st.FindPath(ctx, from, to, maxDepth)
		if err != nil {
			log.Printf("path %s->%s: %v", from, to, err)
			writeJSON(w, http.StatusNotFound, map[string]string{"error": err.Error()})
			return
		}
		writeJSON(w, http.StatusOK, p)
	}
}

func handleDetail(st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		// path: /api/p/<id>/details
		path := r.URL.Path[len("/api/p/"):]
		id := strings.TrimSuffix(path, "/details")
		if id == "" {
			http.Error(w, "id required", http.StatusBadRequest)
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		detail, err := st.GetPersonDetail(ctx, id)
		if err != nil {
			log.Printf("detail %q: %v", id, err)
			writeJSON(w, http.StatusNotFound, map[string]string{"error": err.Error()})
			return
		}
		writeJSON(w, http.StatusOK, detail)
	}
}

func parseIntDefault(s string, d int) int {
	if s == "" {
		return d
	}
	n, err := strconv.Atoi(s)
	if err != nil {
		return d
	}
	return n
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	_ = enc.Encode(body)
}

func withCORS(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		h.ServeHTTP(w, r)
	})
}

func withLog(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		h.ServeHTTP(w, r)
		log.Printf("%s %s %s", r.Method, r.URL.RequestURI(), time.Since(start))
	})
}

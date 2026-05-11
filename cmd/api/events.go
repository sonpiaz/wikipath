package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/start01/wikipath/internal/store"
)

// ─────────── Rate limiter (per session_id, in-memory) ───────────
//
// Token bucket: capacity 100, refilled by 100 tokens per minute. Suitable
// for single-instance dev/local. If we ever go multi-instance the limiter
// state needs to move to Redis or similar.

type sessionLimiter struct {
	mu      sync.Mutex
	buckets map[string]*bucket
}

type bucket struct {
	tokens   int
	lastFill time.Time
}

const (
	bucketCapacity = 100
	bucketRefillPM = 100 // tokens per minute
)

func newSessionLimiter() *sessionLimiter {
	l := &sessionLimiter{buckets: make(map[string]*bucket)}
	go l.gcLoop()
	return l
}

func (l *sessionLimiter) allow(sessionID string, n int) bool {
	l.mu.Lock()
	defer l.mu.Unlock()

	b, ok := l.buckets[sessionID]
	now := time.Now()
	if !ok {
		b = &bucket{tokens: bucketCapacity, lastFill: now}
		l.buckets[sessionID] = b
	}
	// Refill proportional to elapsed time.
	elapsed := now.Sub(b.lastFill).Seconds()
	refill := int(elapsed * float64(bucketRefillPM) / 60.0)
	if refill > 0 {
		b.tokens += refill
		if b.tokens > bucketCapacity {
			b.tokens = bucketCapacity
		}
		b.lastFill = now
	}
	if b.tokens < n {
		return false
	}
	b.tokens -= n
	return true
}

// gcLoop sweeps inactive buckets every 10 minutes to keep the map small.
func (l *sessionLimiter) gcLoop() {
	for range time.Tick(10 * time.Minute) {
		l.mu.Lock()
		cutoff := time.Now().Add(-30 * time.Minute)
		for k, b := range l.buckets {
			if b.lastFill.Before(cutoff) {
				delete(l.buckets, k)
			}
		}
		l.mu.Unlock()
	}
}

// ─────────── Trending cache (in-memory, 5-min TTL) ───────────

type trendingCache struct {
	mu      sync.Mutex
	entries map[string]trendingEntry
}

type trendingEntry struct {
	expiresAt time.Time
	payload   []byte
}

func newTrendingCache() *trendingCache {
	return &trendingCache{entries: make(map[string]trendingEntry)}
}

func (c *trendingCache) get(key string) ([]byte, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	e, ok := c.entries[key]
	if !ok || time.Now().After(e.expiresAt) {
		return nil, false
	}
	return e.payload, true
}

func (c *trendingCache) set(key string, payload []byte, ttl time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.entries[key] = trendingEntry{
		expiresAt: time.Now().Add(ttl),
		payload:   payload,
	}
}

// ─────────── Handlers ───────────

type eventBatchReq struct {
	Events []store.EventInput `json:"events"`
}

func handleEvent(st *store.Store, limiter *sessionLimiter) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		// Body cap at 32KB — way more than a reasonable batch of beacons.
		r.Body = http.MaxBytesReader(w, r.Body, 32*1024)

		var req eventBatchReq
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "invalid body", http.StatusBadRequest)
			return
		}
		if len(req.Events) == 0 {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		if len(req.Events) > 50 {
			http.Error(w, "batch too large (max 50)", http.StatusRequestEntityTooLarge)
			return
		}
		// Rate limit on session_id of the first event (FE always sends same SID
		// per batch). Cost = batch size, so 100 events/min total.
		sid := req.Events[0].SessionID
		if sid == "" {
			http.Error(w, "session_id required", http.StatusBadRequest)
			return
		}
		if !limiter.allow(sid, len(req.Events)) {
			http.Error(w, "rate limit", http.StatusTooManyRequests)
			return
		}

		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		ua := r.Header.Get("User-Agent")
		country := r.Header.Get("CF-IPCountry")
		if len(country) > 2 {
			country = country[:2]
		}
		n, err := st.InsertEvents(ctx, req.Events, ua, country)
		if err != nil {
			log.Printf("event insert: %v", err)
			http.Error(w, "insert failed", http.StatusInternalServerError)
			return
		}
		w.Header().Set("X-Events-Inserted", strconv.Itoa(n))
		w.WriteHeader(http.StatusNoContent)
	}
}

func handleTrending(st *store.Store, cache *trendingCache) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		windowDays := parseIntDefault(r.URL.Query().Get("window"), 7)
		limit := parseIntDefault(r.URL.Query().Get("limit"), 10)
		key := strconv.Itoa(windowDays) + "/" + strconv.Itoa(limit)
		if cached, ok := cache.get(key); ok {
			w.Header().Set("Content-Type", "application/json")
			w.Header().Set("X-Cache", "hit")
			w.Write(cached)
			return
		}

		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		items, err := st.GetTrending(ctx, windowDays, limit)
		if err != nil {
			log.Printf("trending: %v", err)
			writeJSON(w, http.StatusInternalServerError,
				map[string]string{"error": err.Error()})
			return
		}
		buf, _ := json.Marshal(map[string]any{
			"window_days": windowDays,
			"items":       items,
		})
		cache.set(key, buf, 5*time.Minute)
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("X-Cache", "miss")
		w.Write(buf)
	}
}

func handleAdminPopularity(st *store.Store) http.HandlerFunc {
	expected := os.Getenv("ADMIN_TOKEN")
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		if expected == "" {
			http.Error(w, "ADMIN_TOKEN not configured", http.StatusServiceUnavailable)
			return
		}
		auth := r.Header.Get("Authorization")
		token := strings.TrimPrefix(auth, "Bearer ")
		if token == "" || token != expected {
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}
		limit := parseIntDefault(r.URL.Query().Get("limit"), 100)
		missing := r.URL.Query().Get("missing_bio") == "true"

		ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
		defer cancel()
		items, err := st.GetPriorityEnrichment(ctx, limit, missing)
		if err != nil {
			log.Printf("priority: %v", err)
			writeJSON(w, http.StatusInternalServerError,
				map[string]string{"error": err.Error()})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{
			"missing_bio_only": missing,
			"items":            items,
		})
	}
}

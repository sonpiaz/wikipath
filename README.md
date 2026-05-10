# wikipath

Find the shortest chain of Wikipedia mentions between two famous people, streamed live.

A clean-room reimplementation of Rani Saro's [Six Degrees of Wikipedia](https://github.com/Rani-Codes/sixth_degree), built from spec only as a learning project. Simpler than the original on purpose — SSE instead of WebSocket, no graph canvas, no React. ~600 lines of Go + ~150 lines of vanilla web.

## How it works

1. **Crawl** — `cmd/crawl` reads `seeds.txt` (one name per line), hits the public Wikipedia REST API for each, and writes a directed adjacency map to `graph.json`. Edges are kept only if the target is also in the seed set.
2. **Serve** — `cmd/serve` loads `graph.json` into memory and serves three endpoints from a single port:
   - `GET /api/people` — sorted list (full or substring-filtered)
   - `GET /api/search?from=&to=` — Server-Sent Events stream of BFS progress
   - `GET /` — the static SPA
3. **BFS** — level-by-level breadth-first search; each completed level is flushed to the client as one SSE event, then the final path arrives as a `path` event.

## Quickstart

```
# crawl with the bundled 88-person seed list (~30 seconds, polite to Wikipedia)
go run ./cmd/crawl

# serve
go run ./cmd/serve
# then open http://localhost:8080
```

Custom seed list:

```
go run ./cmd/crawl -seeds my-seeds.txt -workers 4 -out my-graph.json
go run ./cmd/serve -graph my-graph.json
```

## Container

```
docker build -t wikipath .
docker run --rm -p 8080:8080 wikipath
```

## Project layout

- `cmd/crawl/main.go`, `cmd/serve/main.go` — entry points
- `internal/wiki/client.go` — Wikipedia API client (User-Agent, retry on 429/5xx with exponential backoff, pagination via `plcontinue`)
- `internal/crawl/pool.go` — goroutine worker pool, edge filtering
- `internal/graph/graph.go` — load + BFS with per-level callback
- `internal/server/server.go` — HTTP handlers + SSE streaming
- `web/` — static SPA, embedded into the binary at build time

## License

MIT.

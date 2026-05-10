# SPEC — sixth-degree

Phase 3 deliverable. Clean-room specification. Team B reads ONLY this file
(plus SPRINT-PLAN.md) when implementing — they never see input/ or analysis/.

## Hard rules for this file

1. NO code blocks longer than 3 lines.
2. NO exact strings longer than 40 characters from source bundles or repos.
3. NO source-repo file paths or function names.
4. Every feature scores 9/9 on the rubric.

## Product overview (3 sentences)

A web app that finds the shortest chain of Wikipedia mentions between any
two famous people in a curated list of ~10,000. The user picks a start and
end name, and the app streams its breadth-first search progress over a live
connection, finally drawing the shortest path on a graph canvas. The
distinction from generic six-degrees-of-Wikipedia tools is the curated
celebrity-only dataset (so every node is recognizable) and the per-level
streaming visualization (so the user sees the search expand outward, not
just the final answer).

## Core user journeys

### Journey 1 — Land on the page
A first-time visitor opens the page and sees a header, two empty name
inputs, an empty log panel, and an empty graph canvas. Within a second the
inputs become typeable. No login is required and no onboarding modal
appears. The footer briefly explains that connections come from Wikipedia
mentions, not real-world meetings.

### Journey 2 — Pick two people
The user clicks the first input and starts typing a name. A debounced
autocomplete (≤300ms) shows up to 50 matching names from the curated list.
Picking a name fills the input and closes the dropdown. The user repeats
for the second input, and the search button transitions from disabled to
enabled, signalled by color and a soft glow.

### Journey 3 — Run a search
The user clicks the search button. A live connection opens to the server,
the log panel prints "connected" and "searching from X to Y", and per-level
progress lines stream in (one summary line per BFS level). When the path
is found, a final success line lists each step joined by an arrow, the
graph canvas highlights the path with larger nodes and a distinct color
spaced apart from the explored nodes, and the search button re-enables for
another query. Total perceived latency on a healthy network is under 5
seconds for a 4-hop path.

### Journey 4 — Adapt to a slow device
On a low-end phone or a 3G link, the client detects the constraint via
browser hints (Save-Data, network type, device memory, CPU concurrency)
and asks the server to skip the heavy adjacency-map payload. The graph
canvas instead grows incrementally as per-level events stream in, so the
visualization is interactive even when the bulk endpoint would have
timed out.

### Journey 5 — Failure recovery
If the user picks a name that's not actually in the graph (typo, stale
copy-paste, or future i18n mismatch) the server returns a single error
message and the client shows it as a red log line. The search button
re-enables immediately so the user can correct and retry. If the live
connection drops mid-search, the client logs "connection closed
unexpectedly" and the user can retry. No partial state persists.

## Tech stack inferred (informational; Team B may differ)

- **Frontend**: a single-page React + TypeScript app, Vite-built, styled
  with utility CSS (e.g. Tailwind), graph rendered with a canvas-based
  graph library plus a separate graph-data library
- **Backend**: a single Go binary serving the API, a streaming endpoint,
  and the static SPA bundle, all on one port
- **Database**: none. A precomputed adjacency map is loaded into memory
  at boot and serves all reads
- **Infra/hosting**: a small container on a simple cloud host (the
  original ran on serverless, then on a basic VM); free-tier-sized

## Features

---

### Feature 1 — Curated person picker

**Priority**: L1

**1. User outcome.** Pick two specific names from a curated list quickly,
without scrolling through 10k entries.

**2. Trigger.** User focuses the start or end input and types ≥1 char.

**3. Inputs.**
- `q` (string, 0–80 chars, case-insensitive) — substring filter
- focus state (which input is active) — drives which state bucket the
  selection lands in

**4. Outputs / side effects.**
- A list of ≤50 candidate names rendered below the input
- On click: input filled, dropdown closes, app state records the pick
- Empty-query focus: returns the full sorted list (paginated UI not
  required at 10k entries; treat as a virtualized scrollable list)

**5. States.**
- idle (input empty, list closed)
- typing (input non-empty, debounce window open)
- loading (debounce fired, request in flight)
- list-shown (results rendered)
- list-empty (no matches)
- selected (input filled, list closed)
- error (request failed; show inline retry hint)

**6. State transitions.**
- idle → typing: keystroke
- typing → loading: 300 ms idle
- loading → list-shown: 200 OK with ≥1 match
- loading → list-empty: 200 OK with 0 matches
- loading → error: non-2xx or network failure
- list-shown → selected: click on a name
- selected → typing: user edits the input again

**7. Error conditions.**
- 4xx: render "couldn't load names" inline; allow retry
- 5xx: same as 4xx with optional "we'll retry automatically" hint
- offline: same; the list can fall back to a baked-in JSON if shipped
- 401: not applicable (no auth)

**8. Boundaries.**
- Max 50 results returned per query while filtering
- Empty-query: full list (≤10,200 names) returned once and cached client-
  side for 5 min
- Debounce 300 ms; client retries 2× on transient failure

**9. Out of scope.**
- Fuzzy matching, typo correction, transliteration
- Image avatars or extra metadata in the dropdown
- Recently-picked / favorites

---

### Feature 2 — Pathfinding search

**Priority**: L1

**1. User outcome.** Get the shortest hop chain between two picked names,
visualized as both a list and a graph.

**2. Trigger.** Both endpoints picked AND user clicks the search button.

**3. Inputs.**
- `startNode` (string, must equal an exact name in the curated list)
- `endNode` (string, must equal an exact name in the curated list)

**4. Outputs / side effects.**
- A live stream of per-level progress messages
- A final success message with the ordered path and its length
- Graph-canvas state updated as messages arrive
- The search button is disabled for the duration of the query

**5. States.**
- idle (no search active)
- connecting (opening live connection)
- searching (receiving level-progress events)
- path-rendering (final-path events arriving)
- done (success or error logged, button re-enabled)

**6. State transitions.**
- idle → connecting: button click
- connecting → searching: connection open + first level event
- searching → path-rendering: final-path event
- path-rendering → done: last final-path event
- any → done(error): error event or socket close

**7. Error conditions.**
- start or end not in graph: server emits an error message
- no path exists: server emits an error message (rare; the curated graph
  is connected by construction but defensive)
- connection drops mid-stream: client logs an error, surfaces a retry
- server timeout: surfaces as an error; retry resets state

**8. Boundaries.**
- Server caps each connection at 15 s of wall time; new search = new
  connection
- BFS depth bound is the natural depth of the graph (≤8 hops observed)
- Max 1 in-flight search per client at a time
- Total streamed messages per query ≤20 in the level-summary mode

**9. Out of scope.**
- Multiple paths (only the first shortest path is returned)
- Weighted edges
- "Explain why this hop exists" narration
- Cancel-mid-search button (search either completes or the connection
  drops; no explicit cancel)

---

### Feature 3 — Streaming progress log

**Priority**: L1

**1. User outcome.** See the search progressing rather than staring at a
spinner.

**2. Trigger.** Live connection opens for a search.

**3. Inputs.** Server-sent message stream (typed as level-summary,
final-path-node, success, error).

**4. Outputs / side effects.**
- A scrolling list of timestamped lines, color-coded info / success /
  error
- Auto-scroll to the newest line; cap at, say, 200 lines

**5. States.** rendering, capped, error.

**6. State transitions.**
- rendering → capped: line count exceeds cap, oldest lines drop
- rendering → error: error event arrives
- error → rendering: next search clears the log

**7. Error conditions.**
- Unknown message type from server: render "unknown event" warning line
- Garbled JSON: render parse-error warning line
- Empty stream: log shows only the "connected" line; user can still retry

**8. Boundaries.**
- 200-line cap (older lines removed)
- 4-color palette (info, success, warn, error)

**9. Out of scope.**
- Persistence across reloads
- Search/filter inside the log
- Export to file

---

### Feature 4 — Graph canvas visualization

**Priority**: L1

**1. User outcome.** See the search frontier expand and the final path
stand out clearly.

**2. Trigger.** Search starts; canvas listens to the same event stream.

**3. Inputs.**
- Per-level event: list of node names added to the explored set
- Final-path event: an ordered list of node names that constitute the
  shortest path
- (Optional) Bulk adjacency map fetched at page load when the device is
  not in reduced-data mode

**4. Outputs / side effects.**
- Nodes drawn as circles, labeled, in two visual classes:
  "explored" (small, muted color) and "path" (larger, distinct color,
  artificially spaced apart along an arc or line)
- Edges drawn between consecutive nodes in the explored frontier (light)
  and along the final path (highlighted)
- Pan + zoom interaction on the canvas

**5. States.** empty, growing, path-highlight, frozen (post-success),
error.

**6. State transitions.**
- empty → growing: first level event
- growing → path-highlight: final-path event
- path-highlight → frozen: last final-path event
- any → empty: new search clears the canvas

**7. Error conditions.**
- Bulk graph fetch fails: silently fall back to streaming-only viz
- Renderer throws: degrade to log-only mode

**8. Boundaries.**
- Hard cap: do not render more than 5,000 nodes simultaneously
- Use a canvas (not SVG) renderer for performance

**9. Out of scope.**
- Click-a-node-to-pivot interaction
- Save/share the rendered graph as an image
- 3D layout

---

### Feature 5 — Reduced-data adaptive mode

**Priority**: L2

**1. User outcome.** The app remains usable on low-end phones and slow
links instead of timing out.

**2. Trigger.** Page load. Client probes browser hints; if any of {network
type is 2g/3g, save-data is on, device memory <4, CPU cores <4} is true,
adaptive mode is on.

**3. Inputs.**
- Browser navigator hints (network info, device memory, CPU)
- Optional explicit query flag the client may set

**4. Outputs / side effects.**
- Bulk adjacency-map fetch is replaced by a 204 short-circuit; the canvas
  builds itself from streamed events instead

**5. States.** unknown, normal, reduced, override.

**6. State transitions.**
- unknown → normal: hints absent or all green
- unknown → reduced: any hint trips
- any → override: user toggles a manual switch (out of scope for v0.1)

**7. Error conditions.**
- Hints API absent: assume normal mode
- 204 received but client thought it asked for full payload: degrade
  silently to streaming-only

**8. Boundaries.**
- Pure client-side decision; server respects an explicit query flag and
  the standard reduced-data request header

**9. Out of scope.**
- A user-visible "fast / data-saver" toggle
- A/B telemetry on which mode users land in

---

### Feature 6 — Self-contained deployable container

**Priority**: L1 (infra)

**1. User outcome.** A single small image runs the whole app: API + live
connection + SPA bundle on one port, no external services.

**2. Trigger.** Operator deploys the image.

**3. Inputs.**
- Build context: source tree + the precomputed adjacency map file
- Optional env: a port override

**4. Outputs / side effects.**
- A static binary serves on a single port
- The SPA is served from the same port with a fallback to the index page
  for client-side routing
- The precomputed adjacency map is bundled into the image

**5. States.** building, running, healthy, fatal-on-missing-graph.

**6. State transitions.**
- start → fatal: graph file missing or corrupt → exit with a clear error
- start → healthy: graph loaded, server listening

**7. Error conditions.**
- Missing graph at startup: hard fail with a single log line
- Port already in use: hard fail
- Graph file present but unreadable (bad JSON): hard fail with a parse
  message

**8. Boundaries.**
- Image size goal: under 25 MB for the final layer (excluding the graph
  file)
- Cold-boot to "ready" goal: under 1 second on a small VM

**9. Out of scope.**
- Health-check probe endpoints (Team B may add `/healthz` if useful)
- Hot-reload of the graph in a running process
- Multiple replicas behind a load balancer

---

### Feature 7 — Crawl pipeline (build-time)

**Priority**: L1 (build), L2 (runtime visibility — none)

**1. User outcome.** A reproducible build step that produces the
adjacency map from a list of seed names. Operator-only; not a user-facing
feature.

**2. Trigger.** Operator runs the crawler binary against a seed file.

**3. Inputs.**
- A newline-delimited file of canonical names (~10k lines), one per line
- Optional concurrency knob (default 10 workers)
- A polite User-Agent string

**4. Outputs / side effects.**
- A JSON file mapping each seed name to its list of seed-name neighbors
  (edges that point to OTHER seed names; the rest of Wikipedia is
  filtered out)
- Per-name progress logged to stdout
- Errors per name logged but do not abort the run

**5. States.** loading-seeds, fetching, aggregating, written, failed.

**6. State transitions.**
- loading-seeds → fetching: seeds parsed and fanned out to workers
- fetching → aggregating: workers complete or stream into the aggregator
- aggregating → written: graph file flushed to disk

**7. Error conditions.**
- Source API rate-limits us: retry with exponential backoff and bounded
  attempts
- Source API returns 5xx: same retry policy
- Seed file missing: hard fail with a clear log
- Per-name fetch fails after retries: skip that name and continue

**8. Boundaries.**
- Worker pool default 10
- Per-request timeout ~30 s, idle connection pool sized for steady state
- Pagination respected via the API's continuation token until empty
- Total runtime target ≤5 min for 10k seeds

**9. Out of scope.**
- Incremental crawl (add new names without redoing all)
- Distributed crawl across multiple machines
- A web dashboard for the crawl

---

## Data model

| Entity | Fields | Relationships |
|---|---|---|
| Person | `name` (string, unique within graph) | many-to-many to Person via `Edge` |
| Edge | `from` (name), `to` (name), direction = directed | belongs to Graph |
| Graph (singleton) | adjacency map keyed by `name` | composed of all Edges |
| PathResult | `path` (ordered Person[]), `length` (int) | derived per query |
| LevelEvent | `level` (int), `nodes` (string[]) | streamed during a query |

Edges are **directed**: A may point to B even if B does not point back
(real Wikipedia link structure is asymmetric). BFS traverses the directed
edges from `start` toward `end`.

## Cross-cutting concerns

### Authentication
None. Public, no accounts. CORS open.

### Permissions / roles
None. Single anonymous user role.

### Pricing / billing surfaces
None. Free public app. The crawl uses a free public API.

### Internationalization
v0.1: English-only labels and English-Wikipedia dataset. The data
pipeline must be encoding-clean (UTF-8 throughout) so future i18n is a
data swap, not a code rewrite.

### Accessibility
- All inputs labeled
- Search button has a clear disabled state with `aria-disabled`
- Color is not the only signal (use icons + text in the log too)
- Canvas: provide a textual fallback (the log already serves this)

### Performance budgets
- p95 perceived latency from "click search" to "first level event": <2 s
- p95 perceived latency from "click search" to "path found": <8 s for a
  4-hop path on broadband
- Server-side per-search wall time: <5 s typical; hard cap 15 s
- Cold container boot: <1 s
- Bulk graph endpoint: short-circuit with 204 on reduced-data signals
- Bundle: <250 KB gzipped for the SPA JS

## Smell test results (filled by Team A before sealing)

### Fresh-session test
- This SPEC is self-contained: a fresh Claude session can implement
  Feature 1, 2, 3, 4 without re-reading source.
- Estimated implementation-choice questions per feature: 1–2.
- Estimated behavior questions per feature: 0.

### Replay test
- 5 user journeys above each fit in 3–5 sentences with explicit states
  and outcomes. Pass.

### Boundary test
- "What if both names are the same?" → Feature 2 input rule (must equal
  exact names) plus the path cap; treat path = [name] length 1 (Team B
  decision; document in implementation notes).
- "What if the user clicks search twice rapidly?" → Feature 2 boundary:
  max 1 in-flight; second click is ignored or replaces the first.
- "What if the graph file is older than the seed file?" → Feature 6
  fatal-on-missing applies only to absence; mismatch is operator's
  responsibility.

### Clean-check
- No code blocks >3 lines.
- No source strings >40 chars.
- No source file paths or function names.

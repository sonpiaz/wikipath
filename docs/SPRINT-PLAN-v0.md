# SPRINT-PLAN — wikipath

Phase 4 deliverable. Team B uses this + SPEC.md to decide what to build first.

Project codename: **wikipath** (set in `.product-name`).

## v0.1 scope

### MUST-HAVE features

- [x] Feature 1 — Curated person picker. Without this, the app can't be
      driven by a non-technical user.
- [x] Feature 2 — Pathfinding search. The whole product.
- [x] Feature 3 — Streaming progress log. Replaces a spinner with insight,
      core to "see the search expand".
- [x] Feature 6 — Self-contained deployable container. Required so the
      app runs anywhere, not just on Son's laptop.
- [x] Feature 7 — Crawl pipeline. Required to produce the adjacency map
      that Feature 2 consumes; one-shot at build time.

### DROP-FOREVER features (anti-features)

- User accounts, sessions, or saved searches
- Multiple-shortest-paths or weighted edges
- "Cancel mid-search" button — connections are short-lived enough
- Mobile-native app
- Payment / billing / rate-limit dashboards

### DEFER to v0.2

- Feature 4 — Graph canvas visualization. Great UX, but the streaming
  log already conveys the search. Skip the canvas-graph dependency for
  v0.1; ship a static HTML "path nodes as a row of cards" instead.
- Feature 5 — Reduced-data adaptive mode. Optimization, not JTBD.
- "Why this hop?" narrative (first-principles wedge below).
- Vietnamese-celebrity dataset (first-principles wedge below).
- WebSocket — replace with HTTP Server-Sent Events for v0.1; simpler,
  one-way, behind any reverse proxy without WS upgrade hassle.

## Tech stack

- **Backend**: Go 1.24, standard library `net/http`. No web framework.
- **Streaming**: HTTP SSE (`text/event-stream`). Skip the WS dependency
  for v0.1; revisit if we need duplex later.
- **Frontend**: vanilla HTML + a small TypeScript file built with esbuild
  (or just plain JS — TBD by Team B). No React/Vite for v0.1; the surface
  is small enough.
- **Styling**: hand-written CSS, no Tailwind. ~150 lines max.
- **Database**: none. Adjacency map is a JSON file loaded at boot.
- **Hosting**: a single Docker image, deployable to a small VM (Render,
  Fly.io, or Son's existing droplet). Single port.
- **Auth**: none.

## Sprints

### Sprint 1 — Crawler + offline graph (1 evening)

**Goal**: produce a working `graph.json` from a smaller seed list (start
with 200 names so the crawl finishes in seconds, not minutes).

**Includes**:
- A seed-name reader
- A Wikipedia link fetcher honoring User-Agent + retry on 429/5xx
- A worker pool (start with 4 workers, configurable)
- An aggregator that filters edges to the seed set and writes JSON

**Acceptance**:
- [ ] `wikipath crawl seeds-200.txt` produces a `graph.json`
- [ ] Re-running the same command twice is deterministic
- [ ] No more than 4 in-flight requests at any time

### Sprint 2 — BFS + SSE server + minimal SPA (1 evening)

**Goal**: a single binary that loads the graph, serves the SPA, and
streams BFS over SSE.

**Includes**:
- BFS with a per-level callback
- HTTP handlers for the static SPA + `/api/people` (substring filter)
  + `/api/search` (SSE stream)
- A vanilla-JS frontend with two `<input list=>` fields, a button, and a
  log panel that listens to SSE events

**Acceptance**:
- [ ] Hồ Chí Minh ↔ Taylor Swift returns a path within 500 ms locally
- [ ] Errors (unknown name) render as a red log line
- [ ] The SPA loads in under 200 ms locally

### Sprint 3 — Container + scale-up to full seed list (half day)

**Goal**: ship a small container; bake the full ~10k seed list.

**Includes**:
- A multi-stage Dockerfile with a final scratch (or distroless) layer
- The full seed list, crawled, baked into the image at build time
- A README with a one-line `docker run` invocation

**Acceptance**:
- [ ] `docker build` then `docker run -p 8080:8080 wikipath` works
- [ ] Final image under 25 MB (excluding the graph file)
- [ ] Cold-boot to first response under 1 second on a small VM

## First-principles delta (Phase 4 mandatory audit)

> If we did not know "Sixth Degree of Wikipedia" existed and reasoned from
> first principles, what's the minimum spec to solve the user's JTBD?

The JTBD (per `PROBLEM-FIT.md`): for a CS-student persona, ship one polished
side project end-to-end (crawler + algorithm + UI + deploy) in <2 weeks.
Strip everything that's not on that critical path.

### Things in SPEC.md but NOT in the first-principles answer

Candidates for DROP-FOREVER (or DEFER to v0.2):

- **Graph canvas visualization (Feature 4).** Spectacular UX but adds two
  third-party graph libraries and most of the rendering complexity. The
  log + a row of cards conveys the result. **DEFER.**
- **WebSocket protocol (in Feature 2).** Duplex isn't needed; the server
  pushes, the client receives. SSE is half the surface area. **REPLACE.**
- **Reduced-data adaptive mode (Feature 5).** Server-side header sniffing
  and client-side hint probing are real engineering, but for a v0.1 with
  10k names we can just stream and let the network handle backpressure.
  **DEFER.**
- **The 15-second connection cap (Feature 2 boundary).** A scar from
  Cloud Run's 300 s ceiling. We don't need it on a VM-style host.
  **DROP.**
- **`/api/graph` bulk endpoint (Feature 5 + Feature 4 dependency).** The
  v0.1 SPA doesn't need the full adjacency map up front; it builds the
  view from streaming events alone. **DROP.**

### Things in the first-principles answer but NOT in SPEC.md

Candidates for wedge feature (these match the whitespace in `PROBLEM-FIT.md`):

- **"Why this hop?" — show the actual sentence containing the next name.**
  The user's mental model is "A mentions B because of X". The original
  shows names only. For each adjacent pair in the path, fetch the source
  Wikipedia paragraph at request time and surface the snippet. Wedge
  candidate for v0.2.
- **Vietnamese celebrities + Vietnamese-Wikipedia coverage.** The signature
  demo path "Taylor Swift → Henry Kissinger → Nguyễn Văn Thiệu → Hồ Chí
  Minh" is a happy accident of an English-Wikipedia-only crawl: there
  are no V-pop, NSƯT, or contemporary Vietnamese politicians in the
  dataset. Crawling vi.wikipedia.org and merging would change the demo
  from "neat coincidence" to "actually useful for Vietnamese users."
  Wedge candidate for v0.2.
- **A copy-pasteable share link of a path.** `?from=X&to=Y` URL plus an
  Open Graph image of the path. Lets users post the result to socials.
  Wedge candidate for v0.2.

### Verdict

For v0.1, we are deliberately shipping a **simpler** clone (SSE not WS,
no graph canvas, no reduced-data mode), not a 5%-better one and not a
10x one. The 10x wedge ("why this hop" + Vietnamese coverage + share
links) is explicitly v0.2. This keeps Sprint 1+2 finish-able in two
evenings and respects PROBLEM-FIT's "weekend" envelope.

## Definition of success for v0.1

- [x] Local Docker container boots, loads the precomputed graph, serves
      the BFS endpoint with p95 <500 ms (the PROBLEM-FIT acceptance).
- [x] The signature demo path "Hồ Chí Minh ↔ Taylor Swift" renders in
      the browser via the streaming log within 5 s end-to-end.
- [x] Son writes a one-page retro: what surprised him about goroutines,
      BFS, and Wikipedia API politeness; what he'd do differently.

## Risks + mitigations

- **Risk**: Wikipedia API rate-limits stop the crawl mid-way.
  - Mitigation: start with a 200-name seed list (≤200 requests, no
    pagination headache); only scale to 10k after the small one works
    end-to-end.
- **Risk**: graph file becomes too large to embed in a tiny image.
  - Mitigation: target 200-name graph for v0.1 (~200 KB), defer 10k.
- **Risk**: Son spends a weekend building Feature 4 (graph canvas) and
  ships nothing.
  - Mitigation: v0.1 explicitly DEFERS Feature 4. If the rest works,
    Feature 4 becomes its own weekend.
- **Risk**: SSE doesn't replay on reconnect, so a dropped connection
  loses progress.
  - Mitigation: each search starts a fresh request; lost progress means
    a 1-click retry. Acceptable for v0.1.

## Phase 5 instructions for Team B

Mode is **MODE 1 (No Wall)**, so Team B may be the same Claude session.
Even so, the discipline holds:

- Read SPEC.md + this SPRINT-PLAN.md as the source of truth.
- The clone repo lives at `~/wikipath/`, NOT inside `~/teardowns/`.
- Initial commit message: `chore: initial scaffold from clean-room spec`.
- Add a `LICENSE` file (MIT) at commit #1.
- If the spec has a gap, mark it in `~/wikipath/SPEC-GAPS.md` and ask
  before guessing.

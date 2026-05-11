# wikipath

**Vietnamese family-tree explorer.** Open data, source-cited, contribution-friendly.

wikipath is a public reference for the family relationships of notable
Vietnamese people — kings, scholars, artists, politicians, athletes.
Search a name, view their family tree visually, find the relationship
path between any two people, and trace every fact back to its source.

> Status: **pre-alpha**, local development. Public site coming to
> **[wikipath.app](https://wikipath.app)**. SPEC v1.2 in [SPEC.md](SPEC.md);
> 8 features locked. A seed dataset (~6,000 persons, ~250 bios, ~1,500
> avatars) is included; full bio enrichment runs on demand against a
> Kyma API key.

## Features

| | Feature | What it does |
|---|---|---|
| F1 | **Multi-source data pipeline** | Wikidata + Wikipedia VN + LLM extraction + community contributions; every fact carries a source-sentence quote |
| F2 | **Diacritic-aware search** | `ng phu trong` matches "Nguyễn Phú Trọng"; alt-name index covers tên hiệu, miếu hiệu, bút danh |
| F3 | **Family tree visualization** | Vertical layout, era-aware coloring, 4 generations up + 3 down by default |
| F4 | **Detail modal** | Quick stats, source badges, "Mở cây từ đây" / "So sánh quan hệ" actions |
| F5 | **Compare / family-path** | Shortest path between any two people, with Vietnamese kinship labels |
| F6 | **Tiered community contribution** | Anonymous Suggest → authenticated Edit → trusted Moderate, with permanent audit log |
| F7 | **Avatar rendering** | Wikidata P18 photos via Wikimedia Commons, monogram fallback |
| F8 | **Engagement analytics** | Anonymous event tracking → popularity-driven enrichment priority |

## Schema highlights (Vietnamese-aware)

The data model reflects Vietnamese kinship conventions rather than
mapping to Western defaults:

- **Đa thê (rank)** — multiple spouses ordered by rank (chính / thứ)
- **Names by kind** — tên húy, tên hiệu, tên thụy, miếu hiệu, pháp danh,
  bút danh, tên cúng cơm
- **Half-siblings** — `sibling_paternal` (cùng cha khác mẹ) vs
  `sibling_maternal` (cùng mẹ khác cha) vs `sibling_full`
- **Child kinds** — birth / adopted / step / foster / ritual_kin
- **Historicity** — confirmed / probable / legendary / mythological
- **Era + dynasty** — Lý, Trần, Lê, Mạc, Trịnh, Tây Sơn, Nguyễn, Hiện đại

See [SPEC.md §3](SPEC.md#3-data-model-vietnamese-aware) for the full schema.

## Architecture

```
                       SPARQL                         User browser
                          │                                 │
     Wikidata ─────► import_wikidata.py                     │
                          │                                 ▼
  Wikipedia VN ─► import_wiki_vi.py / enrich_async.py ─► Next.js (app/)
                          │                                 │
                          ▼                                 │ fetch /api/*
                   DuckDB (wikipath.duckdb) ◄──────►  Go API (cmd/api)
                          ▲                                 │
                          └─────── analytics events ◄───────┘
```

- **Backend**: Go 1.24 + stdlib `net/http`, talks to DuckDB via
  [`go-duckdb/v2`](https://github.com/marcboeker/go-duckdb). One binary,
  five routes: `/api/search`, `/api/p/<id>`, `/api/p/<id>/details`,
  `/api/path`, plus engagement endpoints `/api/event`, `/api/trending`,
  `/api/admin/popularity`.
- **Read store**: DuckDB embedded; recursive CTEs for ancestor/descendant
  collection; <50ms p95 for a 4-up + 3-down tree.
- **Frontend**: Next.js 16 App Router + Tailwind v4 + shadcn/ui +
  `@xyflow/react` for the tree.
- **Data pipeline**: Python (asyncio + aiohttp) for bulk SPARQL imports
  + LLM enrichment via the [Kyma API](https://api.kymaapi.com) gateway.
  Default extraction model: `deepseek-v4-pro`. See "LLM model choice"
  below for a benchmark of stable alternatives.
- **Hallucination guard**: every LLM-extracted fact must include a
  `source_sentence` field that is a literal substring of the input
  article; confidence is downgraded when the match is partial; names
  failing the `is_valid_person_name()` filter are rejected at insert
  time.

## LLM model choice

The enrichment pipeline talks to any OpenAI-compatible chat completions
endpoint. We use the [Kyma API](https://api.kymaapi.com) gateway because
it's Vietnamese-friendly (Asia-region latency, multilingual model
catalog) and lets us swap underlying models without touching code —
just change the `LLM_MODEL` constant in `scripts/enrich_async.py`.

We benchmarked four Kyma-hosted models on the same Wikipedia VN
extraction task (3 articles, identical prompt + JSON schema, 60s
per-request timeout, results from
`python3 scripts/bench_models.py`):

| Model | OK rate | Median latency | Source-sentence match | Notes |
|---|---|---|---|---|
| `deepseek-v4-pro` (preview) | 99.5% (200-profile pilot) | ~5s | high | Current production default |
| `deepseek-v3` (stable) | **3/3 in bench** | 14.3s | 100% | Verified drop-in alternative |
| `gemini-2.5-flash` | 1/3 | 43.8s | 100% | Intermittent timeouts on long articles |
| `glm-4.5-air` | 1/3 | 32.5s | 100% | Intermittent on long articles |
| `qwen-3.6-plus` | 0/3 | – | – | Did not return valid JSON in our bench |

Recommendation: keep `deepseek-v4-pro` as the production default for
quality; switch to `deepseek-v3` if you want a stable-tier model with
the same vendor; the others are not yet recommended for VN-language
structured extraction without further tuning.

To re-run the bench against your own model shortlist:

```bash
python3 scripts/bench_models.py --models deepseek-v3 gemini-2.5-flash
```

## Quick start (local dev)

Requirements: Go 1.24+, Python 3.11+, Node 20+, DuckDB CLI, pnpm.

```bash
# 1. Clone + install
git clone https://github.com/start01/wikipath.git
cd wikipath
cd web && pnpm install && cd ..

# 2. Initialize DuckDB schema
duckdb wikipath.duckdb < internal/schema/001_init.sql
duckdb wikipath.duckdb < internal/schema/002_engagement.sql

# 3. Seed with 49 hand-curated profiles
pip install duckdb PyYAML
python3 scripts/seed_db.py

# 4. Build + run the Go API
go build -o bin/wikipath-api ./cmd/api
./bin/wikipath-api -db wikipath.duckdb -addr :8090

# 5. In another shell, run the Next.js dev server
cd web && pnpm dev --port 3010
# open http://localhost:3010
```

Optional larger dataset (~5,000 persons, requires a Kyma API key in
`KYMA_API_KEY`):

```bash
# Wikidata bulk import (~3 min)
python3 scripts/import_wikidata.py

# Image enrichment (~16s)
python3 scripts/import_images.py

# Bulk LLM enrichment of biographies (~3h wall time, ~$7 LLM cost
# at concurrency 15 against a Vietnamese-language model)
python3 scripts/pick_candidates.py --limit 5000 -o data/candidates-5k.json
python3 scripts/enrich_async.py --candidates data/candidates-5k.json --concurrency 15
```

Note: DuckDB serializes file locks across processes. Stop the Go API
before running batch Python scripts; restart afterwards.

## Project layout

```
wikipath/
├── cmd/api/              # Go HTTP API (read-write DuckDB)
├── internal/
│   ├── schema/           # SQL migrations (001_init, 002_engagement)
│   └── store/            # DuckDB query layer (search, tree, detail, path, events)
├── scripts/              # Python data pipeline
│   ├── seed_db.py
│   ├── import_wiki_vi.py
│   ├── import_wikidata.py
│   ├── import_images.py
│   ├── pick_candidates.py
│   ├── enrich_async.py
│   └── cleanup_bad_llm_names.py
├── web/                  # Next.js 16 frontend
│   ├── app/              # routes: / | /p/[id] | /path/[from]/[to]
│   ├── components/       # SearchBox, FamilyTree, PersonModal, …
│   └── lib/              # api.ts, track.ts, utils
├── data/
│   └── seed-vi.yml       # 49 hand-curated profiles
├── docs/
│   ├── SPEC-v0-celebrity-hops.md
│   └── SPRINT-PLAN-v0.md
├── SPEC.md               # v1.2 design + execution plan
├── PRIVACY.md            # subject + user-data privacy
├── TERMS.md
├── CODE-OF-CONDUCT.md
├── CONTRIBUTOR-AGREEMENT.md
├── TAKEDOWN.md
├── LICENSE               # MIT (code)
├── LICENSE-DATA          # CC BY-SA 4.0 + ODbL (database)
└── DATA-SOURCES.md
```

## Contributing

We accept contributions at three tiers — see
[CONTRIBUTOR-AGREEMENT.md](CONTRIBUTOR-AGREEMENT.md):

- **Tier 0 — Suggest**: anonymous, no login. Submit a correction or
  addition with an optional source URL.
- **Tier 1 — Edit**: authenticated via magic email link, requires CLA
  acceptance, edits enter a moderation queue.
- **Tier 2 — Moderate**: trusted reviewers approve/reject pending edits.

All contributions are bound by the [Code of Conduct](CODE-OF-CONDUCT.md).
The short version: cite or stay quiet; respect Vietnamese cultural
conventions; living people deserve stronger privacy defaults than the
deceased.

## Privacy

- **About persons in the database**: living-by-default is `opt_out`;
  takedowns honored within 7 days. See [PRIVACY.md §1](PRIVACY.md).
- **About visitors of the site**: anonymous `session_id` only, no PII,
  90-day retention, opt-out via localStorage. See
  [PRIVACY.md §2](PRIVACY.md).

## Licenses

- **Code**: [MIT](LICENSE).
- **Database compilation**: dual-licensed under
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
  and the [Open Database License](https://opendatacommons.org/licenses/odbl/1-0/).
  See [LICENSE-DATA](LICENSE-DATA).
- **Upstream data**: Wikipedia (CC BY-SA), Wikidata (CC0), Wikimedia
  Commons (per-file). Attribution preserved in source badges on every
  person modal. See [DATA-SOURCES.md](DATA-SOURCES.md).

## A note on the v0 archive

The original `wikipath` repo was a clean-room reimplementation of the
"Six Degrees of Wikipedia" pattern — celebrity-hop BFS over a
Wikipedia-mention graph. The v0 SPEC + sprint plan are preserved in
`docs/SPEC-v0-celebrity-hops.md` and `docs/SPRINT-PLAN-v0.md` for
historical reference; the v0 source code was removed when the project
pivoted to the Vietnamese family-tree explorer in May 2026. v1 was
written fresh against the new SPEC — no v0 source is imported by the
current codebase.

## Contact

Takedown / correction requests: see [TAKEDOWN.md](TAKEDOWN.md).
Other inquiries: open an issue at https://github.com/start01/wikipath/issues.

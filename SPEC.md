# wikipath — SPEC v1

**Vietnamese family tree + relationship explorer.** Open-data, community-curated.

> v0 = celebrity-hop-chain Wikipedia mention BFS. Shipped 2026-05-10 as
> proof of stack. Archived in `docs/SPEC-v0-celebrity-hops.md`. v1 below
> is the real product; reuses v0's Go/SSE/DuckDB skeleton.

## 1. Positioning (1 paragraph)

Public, open-data application để tra cứu cây gia phả của người Việt nổi
tiếng (vua chúa, chính trị gia, nghệ sĩ, doanh nhân, KOL). Khác 8 player
hiện tại (đều positioning private "tạo gia phả nhà bạn"): wikipath là
public reference + viral discovery tool. Khác Entitree (global,
English-Wikidata-only): Vietnamese-first, multi-source enrichment, native
cultural conventions (đa thê, tên húy, dòng họ + chi + đời, triều đại).

## 2. Core scope (5 features locked)

| # | Feature | Phase |
|---|---|---|
| F1 | **Data enrichment pipeline** — Wikidata + Wikipedia VN + LLM + community | core |
| F2 | **Search** — Person-only filter, mất dấu fuzzy, 3-tier grouping | core |
| F3 | **Family tree** — vertical, era-aware, VN cultural | core |
| F4 | **Detail modal** — quick stats, source citations, contribute action | core |
| F5 | **Compare / family-path** — BFS over relations table (cross-over from v0) | v0.2 |
| F6 | **Community contribute** — auth, edit form, audit log, CLA | v0.2 |

## 3. Data model (Vietnamese-aware)

Tables in DuckDB (read-path) + Postgres (write-path, mirrored).

### `person`

| field | type | note |
|---|---|---|
| `id` | uuid v7 | primary key, time-ordered |
| `wikidata_qid` | text nullable | e.g. `Q36014` |
| `wikipedia_vi_url` | text nullable | https://vi.wikipedia.org/wiki/... |
| `birth_name` | text | "Nguyễn Phú Trọng" |
| `current_family_name` | text | "Nguyễn Phú" |
| `original_family_name` | text nullable | nhũ danh cho phụ nữ |
| `lineage_branch` | text nullable | "chi 4" |
| `era` | text | `pre-1500 / 1500-1900 / 1900-1950 / 1950+ / mythological` |
| `dynasty` | text nullable | `Lý / Trần / Lê / Mạc / Trịnh / Tây Sơn / Nguyễn / Hiện đại` |
| `birth_date` | date partial | YYYY, YYYY-MM, YYYY-MM-DD all valid |
| `death_date` | date partial | same |
| `birth_place` | text | district-level minimum |
| `death_place` | text nullable | |
| `bio_short` | text ≤280 | one-tweet summary |
| `bio_full` | markdown | longer narrative |
| `avatar_url` | text nullable | |
| `historicity` | enum | `confirmed/probable/legendary/mythological` |
| `gender` | enum | `male/female/other/unknown` (lưu ý: schema chấp nhận, UI tôn trọng quy ước truyền thống) |
| `is_living` | bool | gates privacy logic |
| `consent_status` | enum | `public/opt_out/private` (default `public` for non-living, `opt_out` for living) |
| `trust_score` | int 0-100 | computed from source confidence |
| `created_at` / `updated_at` | timestamp | |

### `name`

Multiple names per person.

| field | type | note |
|---|---|---|
| `person_id` | fk | |
| `name` | text | |
| `kind` | enum | `birth / courtesy (tên hiệu) / posthumous (tên thụy) / dharma (pháp danh) / pen / nick / cooking_name (tên cúng cơm) / taboo (húy)` |
| `period_start` / `period_end` | date partial nullable | |
| `language` | text | `vi/zh-han/en/...` |

### `relation`

Edges, directed.

| field | type | note |
|---|---|---|
| `id` | uuid v7 | |
| `from_person_id` | fk | |
| `to_person_id` | fk | |
| `kind` | enum | `parent_father / parent_mother / child_birth / child_adopted / child_step / child_foster / spouse / sibling_full / sibling_paternal / sibling_maternal / ritual_kin` |
| `rank` | int nullable | `1=chính, 2=thứ, ...` for spouse/concubine |
| `period_start` / `period_end` | date partial nullable | |
| `source_kind` | enum | `wikidata / wikipedia_vi / news / book / community / oral` |
| `source_ref` | text | URL / book citation / contributor_id |
| `confidence` | int 0-100 | |
| `created_by` | fk contributor nullable | |
| `created_at` | timestamp | |

### `contributor`

| field | type | note |
|---|---|---|
| `id` | uuid v7 | |
| `email` | text unique | |
| `display_name` | text | |
| `lineage_affiliation` | text nullable | `Nguyễn Phú` (self-claimed, gamification only) |
| `trust_tier` | int 0-5 | 0=new, 5=mod |
| `cla_signed_at` | timestamp | required to contribute |
| `created_at` | timestamp | |

### `contribution_log`

Append-only audit log. Public.

| field | type | note |
|---|---|---|
| `id` | uuid v7 | |
| `contributor_id` | fk | |
| `entity_type` | enum | `person / name / relation` |
| `entity_id` | fk | |
| `kind` | enum | `create / edit / delete / approve / reject` |
| `before_payload` | jsonb nullable | |
| `after_payload` | jsonb | |
| `status` | enum | `pending / approved / rejected / auto_approved` |
| `reviewed_by` | fk contributor nullable | |
| `created_at` | timestamp | |

## 4. Data pipeline

### 4.1 Wikidata bulk (Phase 1)

- Source: `dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2`
- Stream parse with `pgzip` + sonic JSON; filter where any of:
  - `P31 = Q5` AND (`P27 = Q881` OR `P19/P20` in VN places)
  - `P31 = Q5` AND `P172 = Q126480` (Vietnamese ethnic group)
  - Historic VN entities (vua, hoàng tộc) without `P27` but with VN-era markers
- Extract claims: `P22 P25 P26 P40 P3373 P569 P570 P19 P20 P39 P166 P21`
- Output: insert into `person` + `relation` + `name` (DuckDB)
- Coverage estimate from probe: 480 unique persons, 26% với ≥1 family relation, **biased toward pre-1900 royals**

### 4.2 Wikipedia VN infobox (Phase 2)

Bridges the 1900-2026 gap (Wikidata coverage <20% there).

- Source: `dumps.wikimedia.org/viwiki/latest/viwiki-latest-pages-articles.xml.bz2`
- Parse only namespace 0 (articles)
- Match templates: `{{Thông tin nhân vật}}`, `{{Thông tin viên chức}}`, `{{Thông tin vua}}`, `{{Thông tin nghệ sĩ}}`, `{{Thông tin diễn viên}}`, etc.
- Extract fields: `cha`, `mẹ`, `vợ`, `chồng`, `con`, `anh chị em`, `tiền nhiệm`, `kế nhiệm`, `triều đại`
- Resolve link targets to `wikidata_qid` (via interwiki) or insert as new community-tier person
- Conflict detection vs Wikidata → flag for moderation
- Re-run weekly via cron (low cost, dump is ~3GB)

### 4.3 LLM enrichment (Phase 3)

For Wikipedia VN articles **without** a structured infobox.

- Pipeline: per article, send full text + system prompt to Kyma `deepseek-v4-pro`
- System prompt: "Extract father, mother, spouses, children, siblings as JSON. Each must include `source_sentence` quote from the article. If unsure, return null."
- Validate: `source_sentence` must literal-substring-match article body
- Confidence score: based on sentence quality + multi-source agreement
- Output: `relation` rows with `source_kind=llm_enrich`, `confidence` ≤80
- Anything <60 confidence → moderation queue, never auto-published

### 4.4 Community contribution (Phase 4 → v0.2)

- Auth: magic email link (Resend). No Google/FB OAuth (user VN dị ứng).
- CLA accept on first sign-in.
- Forms:
  - **Add person**: 8 fields (name, gender, era, dynasty optional, birth/death y, place, source).
  - **Add relation**: pick 2 persons (or create new), kind, rank, source.
  - **Edit existing**: any field, propose change → moderation.
- Auto-approve threshold: 2 independent contributions agree, or contributor `trust_tier ≥ 3`.
- Soft delete only. Audit log permanent.
- Privacy gate: cannot create/edit person with `is_living=true` + `consent_status=public` unless contributor uploads consent proof.

### 4.5 Local development data flow

For day-1 dev without 150GB dump:

```
seed-vi.txt  →  wikipedia-vi-fetch (per-name)  →  parse infobox  →  duckdb local
```

Bootstrap với 200 người Việt nổi tiếng (vua các triều, lãnh đạo, V-pop, tỷ phú). Đủ để test full UX. Bulk Wikidata dump là Phase 1 production task, không block dev.

## 5. Search (F2)

- Backend: Postgres for community write, DuckDB FTS for read.
  - DuckDB FTS5 với custom Vietnamese tokenizer (bỏ dấu, normalize đệm)
  - Mất dấu: "nguyen phu trong" → match "Nguyễn Phú Trọng"
  - Viết tắt: "ng phu trong" → match
  - Levenshtein ≤2 trên token cuối
- Endpoint: `GET /api/search?q=&era=&lineage=&region=&limit=20`
- Response: 3 buckets in single response:
  ```
  { verified: [...], community: [...], suggestion: "Thêm 'X' vào dòng họ?" }
  ```
- Suggestion shape:
  ```
  {
    id, avatar_url,
    name: "Nguyễn Phú Trọng",
    years: "1944–2024",
    role: "TBT ĐCS Việt Nam",
    region: "Đông Anh, Hà Nội",
    lineage: "Nguyễn Phú · chi 4 · đời 17",
    source_badges: ["wikipedia", "wikidata", "community(3)"],
    trust_score: 95
  }
  ```

## 6. Family tree (F3)

- Library: react-flow (controlled, custom node component)
- Layout: vertical (parents up, children down)
- Default: 4 đời lên + 3 đời xuống from ego
- Ego node: 20% larger, border 2px primary, shadow
- Spouse: same row, double-line connector `═`
- Sibling: row 1 grid below ego, single-line connector `─`
- Half-sibling: dashed connector
- Adopted/step: dotted connector
- Era badge top-right of node (color-coded per dynasty)
- Lineage tag below name (`Nguyễn Phú · chi 4 · đời 17`)
- Mobile: column carousel, swipe horizontal through generations
- Click node → `/p/[qid-or-slug]`, re-render tree centered on new ego
- URL pattern: `/p/Q36014` for Wikidata-tied, `/p/c-{uuid}` for community-only
- Era color palette:
  - Lý (gold), Trần (red), Lê (blue), Mạc (purple), Trịnh (green), Tây Sơn (orange), Nguyễn (yellow), Pháp thuộc (gray), Hiện đại (slate)
  - Mythological (faded violet with diagonal stripe)

## 7. Detail modal (F4)

- Avatar 200×200, fallback monogram
- Name (ego) + 2-3 alt names if exists
- Quick stats row: `👨‍👩‍👧‍👦 1 vợ · 2 con · 4 cháu`
- Lineage row: `🌳 Nguyễn Phú · chi 4 · đời 17`
- Era + dynasty row: `🏛️ Hiện đại · Cộng hòa Xã hội Chủ nghĩa Việt Nam`
- Birth/death: dual-line, `📅 14/04/1944 (Đông Anh, Hà Nội) – 19/07/2024 (Hà Nội)`
- Names section (collapsed): tên húy / tên thường gọi / tên hiệu
- Bio: max 3 lines + "đọc thêm" → expand inline
- Source citations: bullet list with kind icon + label (not just emoji)
  ```
  📚 Wikipedia tiếng Việt (truy cập 2026-05-10)
  🏛️ Wikidata Q36014 (snapshot 2026-05-09)
  📰 VNExpress, "Tổng Bí thư Nguyễn Phú Trọng từ trần" (2024-07-19)
  👥 3 đóng góp cộng đồng
  ```
- Action bar (bottom):
  - `[Show tree]` — primary
  - `[Compare]` — secondary, opens person picker
  - `[✏️ Sửa]` — text button, gated by login
  - `[➕ Thêm người thân]` — text button, gated by login
  - `[🚩 Báo lỗi]` — text button

## 8. Compare / family path (F5, v0.2)

- Pick 2 persons (`?from=Q36014&to=Q170978`)
- BFS over `relation` table treating all kinds as undirected for path search
- Output: ordered chain with edge labels
  - "Hồ Chí Minh ─cha─ Nguyễn Sinh Sắc ─cùng đời với─ ... ─chú─ Bảo Đại"
- Common ancestor detection: if BFS finds both reaching shared person → "tổ chung 5 đời"
- OG image: render mini-tree of the path → `/og/path?from=&to=` returns PNG
- Share URL: `/path/Q36014/Q170978`

## 9. Stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | Go 1.24 stdlib + existing wikipath skeleton | reuse worker pool, retry, SSE patterns |
| Read DB | DuckDB embedded (file in image) | <50ms 4-deep tree, ~3-5 GB after VN filter |
| Write DB | Neon Postgres on Vercel | multi-writer, audit log, listen/notify for moderation |
| Sync | DuckDB rebuilt nightly from Postgres + Wikidata snapshot | eventual consistency OK; reads not real-time |
| Frontend | Next.js 16 App Router + Tailwind + shadcn/ui | SSR per profile = SEO; OG image via `@vercel/og`; shadcn = clean default |
| Tree viz | react-flow + dagre layout | controllable, mobile-friendly |
| Auth | Resend magic email link | no OAuth friction for VN users |
| Search | DuckDB FTS5 + custom VN tokenizer | <30ms p95 |
| LLM | Kyma `deepseek-v4-pro` via existing API | Son's own infrastructure |
| Hosting | Vercel (Next.js) + Cloudflare R2 (DuckDB file mirror) | edge cache profile pages |

## 10. URL structure

- `/` — landing, search box dominant
- `/p/[id]` — profile + tree (id = Wikidata QID or community UUID)
- `/path/[from]/[to]` — relationship path
- `/lineage/[slug]` — index page per dòng họ ("Nguyễn Phú", "Trần Hưng")
- `/era/[slug]` — index per dynasty ("ly", "tran", "le", "nguyen")
- `/contribute` — authenticated dashboard
- `/about` — manifesto + sources + license
- `/api/search`, `/api/p/[id]`, `/api/path` — JSON endpoints

## 11. License + ToS

- **Code**: MIT (existing LICENSE file).
- **Database compilation**: **CC-BY-SA-4.0** + **ODbL** dual. Forces derivatives open.
- **Individual contributions**: CLA grants project rights to re-license.
- **Privacy**:
  - Living people default `consent_status=opt_out`. Cannot publish without proof of consent.
  - Public figures (politicians, celebrities) can be `consent_status=public` by default but takedown SLA still applies.
  - Right to be forgotten: soft delete + 30-day retention + hard delete.
- **Takedown SLA**: 7 days from email contact. `takedown@wikipath.app` (or wherever).
- **DMCA-equivalent**: Vietnamese Copyright Law procedure, contact form.
- **Audit log**: all edits public per profile, Wikipedia-style history page.
- **Files in repo**: `LICENSE`, `LICENSE-DATA`, `PRIVACY.md`, `TERMS.md`, `CODE-OF-CONDUCT.md`, `CONTRIBUTOR-AGREEMENT.md`, `TAKEDOWN.md`, `DATA-SOURCES.md`.

## 12. Repo layout

```
wikipath/
├── cmd/
│   ├── crawl/         (v0, deprecated; keep for archeology)
│   ├── serve/         (v0, deprecated; replaced by Next.js + new Go API)
│   ├── api/           (NEW: Go API for read-path, DuckDB-backed)
│   ├── import-wikidata/   (NEW: bulk Wikidata dump filter)
│   ├── import-wiki-vi/    (NEW: Wikipedia VN infobox parser)
│   └── enrich-llm/    (NEW: Kyma LLM enrichment runner)
├── internal/
│   ├── schema/        (NEW: DuckDB + Postgres migrations)
│   ├── store/         (NEW: read DuckDB / write Postgres)
│   ├── search/        (NEW: VN tokenizer + FTS query builder)
│   ├── wiki/          (rename from wiki/ → keep, used by importers)
│   └── ...
├── app/               (NEW: Next.js 16)
│   ├── page.tsx
│   ├── p/[id]/page.tsx
│   ├── path/[from]/[to]/page.tsx
│   ├── lineage/[slug]/page.tsx
│   ├── api/...
│   └── components/
├── data/
│   ├── seed-vi.txt        (200 names for local dev bootstrap)
│   └── lineages.yml       (mapping: lineage slug → dynasty + era)
├── docs/
│   ├── SPEC-v0-celebrity-hops.md
│   ├── SPRINT-PLAN-v0.md
│   ├── ARCHITECTURE.md
│   └── DATA-SOURCES.md
├── PRIVACY.md
├── TERMS.md
├── CODE-OF-CONDUCT.md
├── CONTRIBUTOR-AGREEMENT.md
├── TAKEDOWN.md
├── LICENSE
├── LICENSE-DATA
├── README.md
└── SPEC.md (this file)
```

## 13. Order of execution (no time estimates per Son's directive)

Numbered, not timed. Each is one focused session.

1. **Schema** — DuckDB + Postgres migrations + sample data 50 hand-curated VN profiles. Verify queries return correct ancestry/descent.
2. **Wikipedia VN infobox parser** — `import-wiki-vi`. Bootstrap 200-500 profiles from a curated VN names list. Spot check 10 profiles end-to-end.
3. **Search API** — Go endpoint with VN-aware tokenizer. Curl test: "ng phu trong" returns Nguyễn Phú Trọng top.
4. **Tree API** — `/api/p/[id]` returns 4-up + 3-down JSON. Curl test: HCM tree, Bảo Đại tree.
5. **Next.js scaffold** — pages, shadcn install, Tailwind theme (dual mode, Be Vietnam Pro + Lora).
6. **Search UI** — input + 3-bucket suggestion list with sample badges.
7. **Tree UI** — react-flow custom node, ego highlight, era badge, mobile carousel.
8. **Detail modal** — quick stats, source citations, action bar (Show tree/Compare/Edit/Add stubs).
9. **Wikidata bulk import** — `import-wikidata` script. Run against 150GB dump. Verify post-import: ~500 VN profiles, era distribution matches probe.
10. **LLM enrichment** — `enrich-llm` calling Kyma. Backfill profiles with no infobox.
11. **Compare/path UI** — F5 ship.
12. **Auth + community contribute** — F6 ship.
13. **Policy docs** — write all `.md` files in repo, link from footer.
14. **Deploy** — Vercel + Neon. Soft launch to 5 trusted users.

Each item should fit in 30-90 minutes solo. If something blows past that, stop and rescope; don't push.

## 14. Out of scope (anti-features)

- Private family-only mode (8 competitors do this; we are explicitly public-by-default)
- Mobile native app
- Paid tier in v0.x
- DNA matching
- Government records integration
- Lunar calendar primary mode (support secondary for display, never as canonical date)
- Feng shui / lucky day analyses (Phả Tuệ does this; not our positioning)
- Chat / forum / messaging
- Photo restoration

## 15. Definition of done for v0.1 launch

- [ ] 200+ VN profiles loaded via Wikipedia VN infobox parser
- [ ] Search "ng phu trong" returns Nguyễn Phú Trọng top in <100ms
- [ ] Tree view renders 4-up + 3-down for ≥50 famous figures
- [ ] Mobile carousel works on iPhone Safari
- [ ] All 5 demo paths render correctly: Hồ Chí Minh, Bảo Đại, Lý Thái Tổ, Trần Hưng Đạo, Nguyễn Phú Trọng
- [ ] PRIVACY/TERMS/LICENSE-DATA committed before any public profile published
- [ ] Deployed to Vercel preview, share URL works

## 16. Open questions (answer before starting #1)

1. **Domain**: all short candidates đã registered. Pick: bid `coi.app` secondary market, or use longer alternative `wikipath.app` / `wikipath.vn`? Recommend `wikipath.vn` for now (consistent with repo, .vn signals Vietnamese-first).
2. **Hosting cost**: DuckDB file in image = ~3-5GB → Vercel Functions image limit might bite. Alternative: serve DuckDB from Cloudflare R2 + load on demand. Decide after Phase 1 import.
3. **Coverage of living political figures**: Nguyễn Phú Trọng family is sensitive (children/spouses publicly known but data scattered). Ship public or opt-out? Recommend `consent_status=public` for documented public figures with `is_living=true`, but flag for manual review pre-publish.
4. **i18n**: VI primary, EN as compat second? Recommend VI-only for v0.1 (focus = Vietnamese audience), EN as v0.2 after community proves traction.

---

## Migration from v0

What to **keep** from current wikipath repo:
- Go module + standard library HTTP patterns
- Worker pool pattern (`internal/crawl/pool.go` → reuse for `import-wikidata`)
- Retry+backoff client (`internal/wiki/client.go` → rename to `internal/external/wikipedia.go`)
- BFS algorithm (`internal/graph/graph.go` → reuse for F5 path search, swap data source)
- SSE patterns (`internal/server/server.go` → reuse for streaming long imports)

What to **deprecate**:
- `cmd/crawl` (v0 celebrity-hop crawler) → archive in `docs/`
- `cmd/serve` (v0 SSE-based BFS server) → replaced by `cmd/api` + Next.js
- `web/` static SPA → replaced by `app/` Next.js
- `seeds.txt` (88 global celebrities) → replaced by `data/seed-vi.txt`
- `graph.json` (mention adjacency) → deleted, no longer canonical

Initial v1 commit message: `feat: pivot to Vietnamese family tree + relationship explorer`.

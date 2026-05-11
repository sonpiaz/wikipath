# wikipath — SPEC v1

**Vietnamese family tree + relationship explorer.** Open-data, community-curated.

> v0 = celebrity-hop-chain Wikipedia mention BFS. Shipped 2026-05-10 as
> proof of stack. Archived in `docs/SPEC-v0-celebrity-hops.md`. v1 below
> is the real product; reuses v0's Go/SSE/DuckDB skeleton.

## Changelog

- **2026-05-10 (v1.2.2)** — First public deploy. New §13.6 documents production hosts, storage, DNS, build pipeline. §15 Deploy criteria checked off (Vercel + Fly live). §16 Q6 records the launch decision: path β (defer Postgres write-path migration) — single Fly VM keeps DuckDB as sole writer until traffic or contribution writes require option (a). Live URLs: `wikipath.app` (Vercel/Next.js), `api.wikipath.app` (Fly/Go).
- **2026-05-10 (v1.2.1)** — Public README rewritten for v1 (was v0 Six-Degrees pitch); 8 features summarized, schema highlights, architecture diagram, quick start, contribution tier explanation, license + privacy summary, v0 archive note. §16 adds open question 6: DuckDB single-writer lock architecture trade-off (with three production options for #14 evaluation). Competitor-name cleanup pass: removed specific names (Grokipedia, Entitree, Plausible, Posthog, Phả Tuệ) from public SPEC + PRIVACY; positioning reframed in generic-category terms.
- **2026-05-10 (v1.2)** — Added §1.1 positioning context (where wikipath sits among adjacent product categories) with moat thesis (provable provenance + VN cultural depth + open data). Added §1.2 design influences (minimalist landing, footer counter, low-friction Suggest path, dark + serif theme). §4.4 community contribution restructured into 3 tiers: Tier-0 Suggest (anonymous, 0-auth), Tier-1 Edit (auth + CLA), Tier-2 Moderate (trust ≥ 3). §10 URL adds footer counter requirement.
- **2026-05-10 (v1.1)** — Added F7 (avatar/image rendering) + F8 (engagement analytics). New §17 covers event taxonomy, scoring algorithm, backend endpoints, FE instrumentation, privacy, and priority-enrichment use case. §3 adds `event` + `person_popularity` tables. §4 adds §4.6 image import, §4.7 scholar pool expansion (P106 occupation filter + birth year 1200-2010), §4.8 LLM enrichment hardening (name filter). §11 privacy split into subject-data + user-data. §13 execution list reorganized: steps 1-10b marked complete, steps 10c-10k forward plan (filter, image import, FE avatar, engagement schema, backend, tracker, refresh job, candidate pool expansion, bulk enrichment to 5k bios). §13.5 ongoing operations: popularity-driven enrichment loop after 30 days of traffic. §15 done targets bumped (5k bios, 3k avatars, false-positive <1%, engagement instrumented). §16 questions resolved 3 of 4, added 5 new.
- **2026-05-09 (v1.0)** — Initial v1 SPEC. Pivot from v0 celebrity-hops to VN family tree. 5 features (F1-F6).

## 1. Positioning (1 paragraph)

Public, open-data application để tra cứu cây gia phả của người Việt nổi
tiếng (vua chúa, chính trị gia, nghệ sĩ, doanh nhân, KOL). Hai khác biệt
chính so với phần lớn ứng dụng gia phả hiện có: (1) public reference +
viral discovery tool thay vì private "tạo gia phả nhà bạn", và (2)
Vietnamese-first với multi-source enrichment và native cultural
conventions (đa thê, tên húy, dòng họ + chi + đời, triều đại) thay vì
English-first generic Wikidata views.

### 1.1 Positioning context

wikipath occupies a niche that adjacent products do not fill:

| Adjacent category | What it provides | Gap wikipath fills |
|---|---|---|
| **Wikipedia VN** (upstream source) | Human-edited, broad encyclopedia | No relationship graph UI; family info buried in prose. wikipath consumes Wikipedia as a source and surfaces relations visually. |
| **Wikidata** (upstream source) | Structured, global, English-primary claims | Sparse for post-1900 VN, no narrative bio, no VN-aware schema (đa thê, tên húy, dòng họ + chi + đời). wikipath consumes Wikidata and adds a VN cultural layer. |
| **Global Wikidata-based tree explorers** | English-first family-tree UIs | No VN cultural conventions, no narrative bio, no community contributions on top of Wikidata. wikipath is VN-native, multi-source, and contribution-friendly. |
| **LLM-generated general encyclopedias** | Single-LLM authority, broad coverage, closed-edit | No per-claim source-sentence citation, no VN cultural depth. wikipath inverts this: every fact carries a literal source-sentence quote and the contribution model is open. |
| **Private "build your own gia phả" apps** | Personal family tree for end users | Private and paid; no public reference data layer. wikipath sits one level upstream as a public discovery layer that can interoperate with private apps. |

**Moat thesis**: wikipath wins on three deliberate choices —
**provable provenance** (every fact has a source-sentence quote, see §4.8),
**Vietnamese cultural depth** (the schema models đa thê, tên húy/hiệu/posthumous/temple/dharma/pen, dynasty, lineage branch, see §3),
and **open data** (CC BY-SA + ODbL dual license, see §11). These are forcing functions: a competitor cannot match all three at once without committing to the same trade-offs.

### 1.2 Design influences

Selected patterns we adopt because they match the audience and quality bar:

- **Minimalist search-first landing**: input centered, trending + recent below. Implemented via cmdk SearchBox (§5, §6).
- **Footer counter as social proof**: `N persons · M relations · K sources` in the landing footer signals data depth at a glance.
- **Low-friction "Suggest" path**: anonymous contribution (no login) for the lowest tier; auth + CLA reserved for edits with audit log. Implements §4.4 Tier 0.
- **Dark mode default for content-heavy reading** with a serif display face (Lora) for person names. Implemented in the global theme.

Principles wikipath commits to (the affirmative form of the same design choices):

- ✅ Every fact carries a literal source-sentence quote, validated server-side as a substring of the input article (see §4.8).
- ✅ Open community editing with a permanent, public audit log (see §4.4).
- ✅ Every source-badge in the UI clicks through to the upstream record (Wikipedia article, Wikidata page, Commons file).
- ✅ Vietnamese-first content authored in Vietnamese; UI labels, kinship terms, and date formats follow Vietnamese conventions.

## 2. Core scope (8 features locked)

| # | Feature | Phase |
|---|---|---|
| F1 | **Data enrichment pipeline** — Wikidata + Wikipedia VN + LLM + community | core |
| F2 | **Search** — Person-only filter, mất dấu fuzzy, 3-tier grouping | core |
| F3 | **Family tree** — vertical, era-aware, VN cultural | core |
| F4 | **Detail modal** — quick stats, source citations, contribute action | core |
| F5 | **Compare / family-path** — BFS over relations table (cross-over from v0) | v0.2 |
| F6 | **Community contribute** — auth, edit form, audit log, CLA | v0.2 |
| F7 | **Avatar / image rendering** — Wikidata P18 → Commons → next/image, monogram fallback | core |
| F8 | **Engagement analytics** — event log + popularity score + priority enrichment queue | core |

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

### `event` (F8 — engagement analytics)

Append-only log of every user interaction. No PII. Powers popularity scoring + priority enrichment + future analytics dashboard. Day-1 schema so we never lose signal.

| field | type | note |
|---|---|---|
| `id` | uuid v7 | |
| `event_type` | enum | `page_view / search / modal_open / tree_expand / node_click / external_click` |
| `person_id` | uuid nullable | target person (null for search-without-result) |
| `query` | text nullable | search string (only for `search` events) |
| `session_id` | varchar(36) | anonymous uuid generated client-side, stored in localStorage |
| `referrer` | text nullable | trimmed to host only (no full URL) |
| `user_agent_hash` | varchar(40) | sha1(UA) — fingerprint without retention |
| `country` | varchar(2) nullable | ISO-3166-1 from CF-IPCountry header |
| `created_at` | timestamp | |

Indexes: `(person_id, created_at)`, `(event_type, created_at)`, `(session_id)`.

**Retention**: rolling 90 days. Events older than 90 days collapsed into `person_popularity` monthly snapshot and hard-deleted.

### `person_popularity` (F8 — derived)

Materialized score table refreshed nightly by `cmd/refresh-popularity`. Read-only from app.

| field | type | note |
|---|---|---|
| `person_id` | uuid pk | |
| `views_24h` | int | last 24h `page_view` count |
| `views_7d` | int | last 7d |
| `views_30d` | int | last 30d |
| `modal_opens_30d` | int | last 30d `modal_open` count |
| `tree_expands_30d` | int | last 30d `tree_expand` count |
| `unique_visitors_30d` | int | `COUNT(DISTINCT session_id)` |
| `last_event_at` | timestamp | most recent event for this person |
| `score` | real | composite, see §17.2 |

Index: `(score DESC)`.

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

Contribution model is tiered by friction. Low-friction = ungated to maximize signal. Quality enforcement happens at moderation, not at submission.

**Tier 0 — Suggest (anonymous, 0 clicks of auth)**

A low-friction "Suggest" path that adds a source-quote requirement so even anonymous submissions remain verifiable:
- "Đề xuất bổ sung" button on every person modal + landing footer.
- Form: free-text description + URL source (optional but encouraged).
- No login required. Captures `session_id` + UA hash + optional contact email.
- Goes into `contribution_log` with `status='pending'`, `kind='suggest'`.
- Rate limit: 5 suggestions per session_id per hour.
- Moderator reviews in batch; high-quality suggestions promoted to actionable edits.

**Tier 1 — Edit / Add (auth required)**

- Auth: magic email link (Resend). No Google/FB OAuth (user VN dị ứng).
- CLA accept on first sign-in.
- Forms:
  - **Add person**: 8 fields (name, gender, era, dynasty optional, birth/death y, place, source).
  - **Add relation**: pick 2 persons (or create new), kind, rank, source.
  - **Edit existing**: any field, propose change → moderation.
- Auto-approve threshold: 2 independent contributions agree, or contributor `trust_tier ≥ 3`.
- Soft delete only. Audit log permanent.
- Privacy gate: cannot create/edit person with `is_living=true` + `consent_status=public` unless contributor uploads consent proof.

**Tier 2 — Moderate (trust_tier ≥ 3)**

- Approve/reject pending suggestions and edits.
- Can flag persons for `consent_status=opt_out` review.
- Activity logged in `contribution_log` with `kind='approve'/'reject'`.

This three-tier model encodes the principle that contribution should be **open but verifiable**: friction scales with the risk of the action, never with the cost of the source-quote requirement.

### 4.5 Local development data flow

For day-1 dev without 150GB dump:

```
seed-vi.txt  →  wikipedia-vi-fetch (per-name)  →  parse infobox  →  duckdb local
```

Bootstrap với 200 người Việt nổi tiếng (vua các triều, lãnh đạo, V-pop, tỷ phú). Đủ để test full UX. Bulk Wikidata dump là Phase 1 production task, không block dev.

### 4.6 Image enrichment (F7)

Wikidata P18 → Wikimedia Commons.

- Script: `scripts/import_images.py`. Input: every `person.wikidata_qid`. Output: populate `person.avatar_url`.
- SPARQL pattern (batched in `VALUES` chunks of 500):
  ```
  SELECT ?p ?image WHERE {
    VALUES ?p { wd:Q1 wd:Q2 ... }
    ?p wdt:P18 ?image .
  }
  ```
- URL format stored: `https://commons.wikimedia.org/wiki/Special:FilePath/{filename}?width=300`
- Coverage expectation: 50-60% of QIDs have P18 (~3,400 of 5,636 current persons). The rest fall back to monogram avatar.
- Re-run quarterly or on-demand after batch import.
- **No local cache**. `next/image` optimizer + Commons CDN handle delivery. `next.config.ts` allowlist:
  ```ts
  images: { remotePatterns: [{ protocol: 'https', hostname: 'commons.wikimedia.org' }] }
  ```
- **Attribution**: every avatar render shows source link via PersonModal (Wikipedia/Wikidata badge already covers it per CC-BY-SA).

### 4.7 Scholar / intellectual pool expansion

Default `pick_candidates.py` filter (`P31=Q5 AND P27=Q881 AND born 1850-2010 AND has P18`) is biased toward modern public figures. Misses pre-modern scholars + diaspora intellectuals. Expansion strategy:

- **Widen birth-year band**: 1200-2010 (cover Lý/Trần/Lê/Mạc scholars). Drop `has-image` requirement for fame proxy.
- **Add occupation filter** (P106 ∈ VN-relevant set):

  | QID | Occupation |
  |---|---|
  | Q901 | scientist |
  | Q170790 | mathematician |
  | Q482980 | author / writer |
  | Q4964182 | philosopher |
  | Q11569986 | academic / professor |
  | Q1622272 | historian |
  | Q49757 | poet |
  | Q1930187 | journalist |
  | Q188094 | economist |
  | Q39631 | physician |
  | Q15976092 | educator |
  | Q864380 | composer |
  | Q36180 | writer (broad) |
  | Q15214752 | diplomat |
  | Q201788 | historian (narrow) |

- **Drop citizenship-only filter for diaspora**: also include `P172=Q126480` (Vietnamese ethnic group) — captures Trịnh Xuân Thuận (UVA astronomer), Ngô Bảo Châu (math, French citizen), etc.
- **Sitelinks as alt fame proxy**: rank by `?sitelinks` count from `?p wikibase:sitelinks ?sitelinks` instead of has-image where image missing.

Names expected to surface from expansion (Son will recognize):
Nguyễn Trãi, Lê Quý Đôn, Chu Văn An, Nguyễn Bỉnh Khiêm, Lê Hữu Trác,
Ngô Bảo Châu, Hoàng Tụy, Phan Đình Diệu, Trịnh Xuân Thuận,
Phan Châu Trinh, Phan Bội Châu, Tản Đà, Xuân Diệu, Nguyên Hồng, Tô Hoài,
Vũ Trọng Phụng, Nam Cao, Thạch Lam, Khái Hưng, Nhất Linh, Hoàng Cầm,
Quang Dũng, Trần Đăng Khoa, Đặng Thái Sơn.

### 4.8 LLM enrichment hardening — name filter

Pilot batch (200 famous, 2026-05-10) returned 99.5% success, avg confidence 89.8, but surfaced **1.7% schema-level false positives** where LLM extracted generic phrases as person names:
- `"6 anh chị em"` as sibling
- `"con trai cả"` as parent
- `"Phan"` (bare surname) as mother

LLM was faithful to source sentences but schema accepted any string as `birth_name`. Fix is name validation post-extract:

```python
GENERIC_PATTERNS = re.compile(
    r"^(các |những |\d+\s)?"
    r"(anh chị em|vợ|chồng|con( trai| gái)?|cha|mẹ|cha mẹ|"
    r"các con|tổ tiên|hậu duệ|cháu|chắt|phu nhân|phu quân)\b",
    re.IGNORECASE,
)

def is_valid_person_name(name: str) -> bool:
    n = name.strip()
    if len(n) < 4: return False                # rejects "Phan", "Lê"
    if re.search(r"\d", n): return False        # rejects "6 anh chị em"
    if GENERIC_PATTERNS.search(n.lower()): return False
    if len(n.split()) < 2: return False         # VN names usually 2-4 tokens
    return True
```

Applied in two places:
1. **Forward guard** (`enrich_async.py`): reject before `find_or_stub_person()` call, so bad names never create stub persons or relations.
2. **Backfill cleanup** (one-time DELETE): remove existing bad rows from pilot batch.

Tradeoff: `≥2 word tokens` reject some mononyms (rare in VN — most royals use full 2-4 char names). Acceptable for v0.1. If false negatives surface, weaken to `≥2 words OR ≥6 chars`.

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

## 6.1 Avatar rendering on tree nodes (F7)

- PersonNode header: 32px circular avatar to the left of name.
- Source: `person.avatar_url` (Wikidata P18 → Commons Special:FilePath, see §4.6).
- Component: `next/image` with `width=64 height=64` (2x for retina), `unoptimized={false}`.
- Fallback chain:
  1. `avatar_url` present → render image.
  2. Image load error → swap to monogram (initial of `birth_name` last token, e.g. `T` for Trọng).
  3. SSR safety: always render monogram first; client-side hydrate to image after mount to avoid CLS.
- Ego node: avatar 40px (slightly larger), same fallback.

## 7. Detail modal (F4)

- Avatar 200×200, fallback monogram (same source + fallback chain as §6.1)
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

- `/` — landing, search box dominant, footer shows `N persons · M relations · K sources` social-proof counter (per §1.2)
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
- **Privacy** (subject data — persons in our DB):
  - Living people default `consent_status=opt_out`. Cannot publish without proof of consent.
  - Public figures (politicians, celebrities) can be `consent_status=public` by default but takedown SLA still applies.
  - Right to be forgotten: soft delete + 30-day retention + hard delete.
- **Privacy** (user data — visitors of the site, see §17.5):
  - Anonymous `session_id` only, no PII collection.
  - 90-day raw event retention, then aggregated + deleted.
  - "Không theo dõi tôi" opt-out via localStorage flag.
  - No third-party analytics pixels.
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

Numbered, not timed. Each is one focused session. Steps 1-10b were completed in the 2026-05-09/10 sessions; remainder is forward plan.

### Completed (status = ✅ as of 2026-05-10)

1. ✅ **Schema** — DuckDB migrations + 49 hand-curated VN profiles + 50 relations. Views v_parents/v_children/v_spouses/v_siblings verified.
2. ✅ **Wikipedia VN infobox parser** — `scripts/import_wiki_vi.py`. Templates `{{Thông tin nhân vật}}` + aliases. Resolves to existing QIDs or creates stubs.
3. ✅ **Search API** — Go `cmd/api` on `:8090`. `/api/search` joins `name` table for alt-name match; VN-aware fuzzy lives in DuckDB FTS.
4. ✅ **Tree API** — `/api/p/[id]` recursive CTE, 4-up + 3-down + spouses + siblings.
5. ✅ **Next.js scaffold** — App Router, Tailwind v4, shadcn (radix base). Be Vietnam Pro + Lora + JetBrains Mono. Cream/warm-dark dual theme.
6. ✅ **Search UI** — cmdk Command with `shouldFilter={false}`, 250ms debounce, AbortController, 3-tier grouping.
7. ✅ **Tree UI** — `@xyflow/react` with hand-rolled BFS layout, ego highlight, fitView constrained (minZoom 0.6, maxZoom 1).
8. ✅ **Detail modal** — shadcn Dialog, monogram avatar, stat pills, source badges, action bar.
9. ✅ **Wikidata bulk import** — `scripts/import_wikidata.py`. SPARQL paginated. 307 → 5,826 → 6,038 persons.
10. ✅ **LLM enrichment (sync pilot)** — `scripts/enrich_llm.py` calling Kyma `deepseek-v4-pro`. Source-sentence validation.
10b. ✅ **LLM enrichment async pilot** — `scripts/enrich_async.py`, 200 profiles in 15:25 (14.6× speedup), 99.5% success, avg conf 89.8.

### Forward plan (Son requested 2026-05-10)

10c. ✅ **LLM enrichment name filter** — `is_valid_person_name()` forward guard in `enrich_async.py` (5 call sites wrapped via `resolve()`) + `scripts/cleanup_bad_llm_names.py` backfill (removed 11 invalid persons, 8 bad relations). 20/20 validator smoke tests pass. See §4.8.
10d. ✅ **Image import (F7)** — `scripts/import_images.py` SPARQL P18 batched VALUES. Matched **1,485/5,633 (26.4%)** in 16.4s — lower than my 50% estimate (long tail of obscure VN persons lacks Commons images). Top-tier (HCM, Trần Hưng Đạo, Gia Long, Lê Lợi, etc.) all covered. See §4.6.
10e. ✅ **Avatar FE rendering** — `components/person-avatar.tsx` with monogram fallback (last-token initial) + image error state flip. PersonNode 32px (ego 40px) + PersonModal 96px hero. `next.config.ts` allowlists `commons.wikimedia.org` + `upload.wikimedia.org`. Go store + API surfaces `avatar_url` in Suggestion, TreeNode, PersonDetail. See §6.1, §7.
10f. ✅ **Engagement schema** — migration `internal/schema/002_engagement.sql` adds `event` + `person_popularity` tables with 4+2 indexes. Applied to local DuckDB. API healthcheck OK post-restart. See §3.
10g. ✅ **Engagement backend** — `internal/store/events.go` adds `InsertEvents`/`GetTrending`/`GetPriorityEnrichment`. `cmd/api/events.go` adds 3 routes: `POST /api/event` (batch, 32KB cap, 50/batch, in-memory token-bucket rate-limit 100/min/session), `GET /api/trending` (public, 5-min in-memory cache), `GET /api/admin/popularity` (Bearer ADMIN_TOKEN gate). Store switched to read-write mode (DuckDB serializes file lock either way). CORS extended for POST + Authorization. 6/6 smoke tests pass: invalid event_types silently skipped, score math correct (1 view + 1 modal = 3), unauthorized admin → 403. See §17.3.
10h. ✅ **Engagement FE tracker** — `web/lib/track.ts` with localStorage session_id (uuid), 500ms batch debounce, `navigator.sendBeacon` with `text/plain` Blob (CORS-simple to avoid preflight; server decodes JSON regardless of Content-Type), `wikipath:no-track=1` opt-out. Instrumented 4 call sites: `TrackPageView` client wrapper for server page, `search-box.tsx` after debounced result (with top-result person_id), `person-modal.tsx` on mount, `family-tree.tsx` distinguishes `node_click` (ego) vs `tree_expand` (non-ego). End-to-end verified via headless browse: page navigation + first-child click → 3 entities surface in `/api/admin/popularity` with correct weighted scores (1/2/3/5). See §17.4.
10i. **Popularity refresh job** — Go binary `cmd/refresh-popularity` rebuilding `person_popularity` from 30-day event window. Schedule nightly via launchd (local) → GitHub Action (post-deploy).
10j. **Candidate pool expansion** — modify `scripts/pick_candidates.py` per §4.7 (year band 1200-2010, P106 occupation filter, sitelinks fame proxy fallback, drop has-image hard requirement).
10k. **Bulk enrichment to 5,000 bios** — three async batches (~1,500 each) using expanded pool. Audit gate between batches (5-row random check, false-positive rate ≤3% to proceed). Total ~2.7h wall, ~$7 Kyma cost.
11. 🟡 **Compare/path UI (F5)** — implemented end-to-end, awaiting E2E test once batch enrichment finishes. Backend: `internal/store/path.go` iterative BFS with batched per-level neighbor query (`expandFrontier`), reconstructs ordered path + detects common ancestor heuristic. `cmd/api/main.go` adds `GET /api/path?from=X&to=Y&max=8` with 8s timeout. FE: `web/lib/api.ts` adds `getPath()`+ types; `web/components/path-display.tsx` renders chain with Vietnamese kinship labels (cha của, mẹ của, vợ thứ N của, anh chị em cùng cha của, etc.), highlights endpoints + common ancestor; `web/app/path/[from]/[to]/page.tsx` is the share-able route; `web/components/person-modal.tsx` "So sánh quan hệ" button enabled when modal target ≠ current ego, navigates to `/path/${egoId}/${targetId}`. OG image generator deferred to v0.2.
12. **Auth + community contribute** — F6 ship. Resend magic link, CLA gate, edit/add forms, audit log, moderation queue.
13. ✅ **Policy docs** — 7 files written at repo root:
    - `PRIVACY.md` — subject-data + user-data (§17.5 analytics, 90-day retention, opt-out via localStorage)
    - `TERMS.md` — accuracy disclaimer, allowed/prohibited uses
    - `CODE-OF-CONDUCT.md` — "cite or stay quiet", VN cultural sensitivity, disputed-records policy
    - `CONTRIBUTOR-AGREEMENT.md` — 3-tier CLA (Suggest anonymous / Edit auth / Code MIT)
    - `TAKEDOWN.md` — email channel, 3-day ack / 7-day reply / 30-day hard-delete SLA
    - `LICENSE-DATA` — CC BY-SA 4.0 + ODbL dual, attribution requirements
    - `DATA-SOURCES.md` — provenance: Wikidata / Wikipedia VN / LLM enrich / seed / Commons P18, confidence tiers
    LICENSE (MIT) already present from v0.
14. **Deploy** — Vercel (Next.js) + Neon Postgres (write path) + Cloudflare R2 (DuckDB mirror). Public domain: `wikipath.app` (registered 2026-05-10).

Each item should fit in 30-90 minutes solo. If something blows past that, stop and rescope; don't push.

## 13.5 Ongoing operations (post-deploy)

Once §10f-10i ship and the site has been live ≥30 days, switch the enrichment input source:

- Replace `pick_candidates.py` SPARQL fame proxy with popularity-driven query (§17.6).
- Run `enrich_async.py` weekly on top-200 popular persons missing `bio_short`.
- Audit gate stays the same (random 5-row check after each batch).
- Re-run image import quarterly (cover new community-added persons).
- Wikidata bulk import re-run quarterly to catch upstream edits.

This closes the feedback loop: user interest → enrichment priority → richer data → more interest.

## 13.6 Deploy log (v0.1 — 2026-05-10)

First public deploy. Architecture chose Q6 path β (defer Postgres write-path
migration to post-launch); details in §16 Q6 update below.

**Production hosts**:
- `https://wikipath.app` + `https://www.wikipath.app` — Next.js 16 App Router on
  Vercel (region: auto-edge), project `sonpiazs-projects/wikipath`. Deployment
  `wikipath-ojywihxsj-sonpiazs-projects.vercel.app` aliased to apex + www.
  Auto-issued Let's Encrypt certs.
- `https://api.wikipath.app` — Go binary (`cmd/api`) on Fly.io app
  `wikipath-api`, region `sin` (Singapore — closest to VN audience). Single
  shared-cpu-1x VM, 512MB RAM. Auto-stop on idle (suspend), cold start ~1s.

**Storage**:
- Fly volume `wikipath_data` (1GB, encrypted) mounted at `/data`. Holds
  `wikipath.duckdb` (11MB seed shipped in image, copied to volume on first boot
  via `docker-entrypoint.sh`).

**DNS** (Namecheap, set via API not nameserver delegation):
- `wikipath.app A 76.76.21.21` (Vercel apex)
- `www.wikipath.app A 76.76.21.21` (Vercel www)
- `api.wikipath.app A 66.241.124.159` + `AAAA 2a09:8280:1::113:f392:0` (Fly)

**Build/deploy pipeline**:
- Backend: `fly deploy --remote-only` from repo root. Multi-stage Dockerfile
  (`golang:1.24-bookworm` builder → `debian:bookworm-slim` runtime). 47MB
  final image. CGO required by `marcboeker/go-duckdb/v2`.
- Frontend: `vercel --prod` from `web/`. Turbopack build, ~10s. Single env var
  `NEXT_PUBLIC_WIKIPATH_API_URL=https://api.wikipath.app` (baked into client
  bundle).

**What's not yet deployed**:
- Postgres write-path (Q6 option a) — deferred per launch decision; current
  setup means Python batch enrichment must stop the API to acquire DuckDB lock.
  Acceptable while traffic is low and enrichment is manual.
- `cmd/refresh-popularity` cron — popularity scores recomputed only on demand
  via `/api/admin/popularity?refresh=true` (when added).
- Engagement opt-out UI (Q3) — to ship before any external launch announcement.

## 14. Out of scope (anti-features)

- Private family-only mode (8 competitors do this; we are explicitly public-by-default)
- Mobile native app
- Paid tier in v0.x
- DNA matching
- Government records integration
- Lunar calendar primary mode (support secondary for display, never as canonical date)
- Feng shui / lucky day analyses (out of scope; some private gia phả apps offer this — wikipath does not)
- Chat / forum / messaging
- Photo restoration

## 15. Definition of done for v0.1 launch

### Data
- [x] 200+ VN profiles loaded via Wikipedia VN infobox parser
- [x] Wikidata bulk import scaled to ≥5,000 persons
- [ ] ≥5,000 persons with `bio_short` populated (currently 257; target via §10k batches)
- [ ] ≥3,000 persons with `avatar_url` populated (via §10d)
- [ ] LLM enrichment false-positive rate <1% after §10c filter (currently 1.7%)

### Search + tree
- [x] Search "ng phu trong" returns Nguyễn Phú Trọng top in <100ms
- [x] Tree view renders 4-up + 3-down for ≥50 famous figures
- [ ] Mobile carousel works on iPhone Safari
- [ ] All 5 demo paths render correctly: Hồ Chí Minh, Bảo Đại, Lý Thái Tổ, Trần Hưng Đạo, Nguyễn Phú Trọng
- [ ] Scholar demo paths added: Nguyễn Trãi, Lê Quý Đôn, Ngô Bảo Châu, Phan Châu Trinh, Tô Hoài

### Engagement + analytics
- [ ] `event` + `person_popularity` tables shipped from day 1
- [ ] `/api/event` accepts beacon POSTs with rate limit
- [ ] 4 instrumentation points firing (page_view, search, modal_open, tree_expand)
- [ ] `/api/trending` cached endpoint returns top-10 last-7d on landing
- [ ] "Không theo dõi tôi" opt-out documented + functional

### Policy
- [ ] PRIVACY/TERMS/LICENSE-DATA committed before any public profile published
- [ ] PRIVACY explicitly covers §17.5 user-behavior tracking + opt-out

### Deploy
- [x] Deployed to Vercel production, `https://wikipath.app` returns 200
- [x] Go API live at `https://api.wikipath.app/healthz`, search/tree/trending verified
- [ ] Cron job for nightly popularity refresh confirmed running

## 16. Open questions

Resolved (2026-05-09/10 sessions):

- ~~**Domain**~~: `wikipath.app` registered 2026-05-10. Local-first dev continues until deploy.
- ~~**Hosting cost**~~: keep DuckDB local during dev. Decide R2 vs in-image at deploy step (§14).
- ~~**i18n**~~: VI-only for v0.1, EN deferred to v0.2.

Still open:

1. **Coverage of living political figures**: Nguyễn Phú Trọng family is sensitive (children/spouses publicly known but scattered). Default `consent_status=public` for documented public figures with `is_living=true`, but flag for manual review pre-publish. **Final policy to lock before §14 deploy.**
2. **Admin token**: `/api/admin/popularity` needs a bearer token. Pick: env var `ADMIN_TOKEN` (simple, OK for solo) or short-lived signed JWT (overkill v0.1). Recommend env var, rotate quarterly.
3. **Engagement opt-out UI placement**: footer link vs. cookie banner vs. settings page (no settings page until F6). Recommend footer link → simple toggle, no modal, no banner.
4. **Wikidata P18 license edge cases**: most Commons images are CC-BY-SA, some are PD, a few non-free fair-use. SPARQL doesn't return license metadata. Risk: rendering a non-free image without attribution. Mitigation: trust Commons curation (they don't usually host non-free at FilePath), and always link to Commons page from PersonModal. **Decision: ship with that mitigation, revisit if takedown received.**
5. **Sitelinks fame proxy threshold**: at what `?sitelinks` count does a person stop being "notable" for our purposes? Empirical: pre-modern scholars often have ≤5 sitelinks but are clearly notable. Recommend no hard floor in v0.1; rely on user popularity signal post-launch to demote noise.
6. **DuckDB single-writer lock (production architecture)**: the v0.1 store opens DuckDB in `read_write` mode so the same process can serve reads (search, tree, detail, path) and write engagement events. DuckDB serializes file locks across processes, so the Python batch pipeline (`scripts/import_*`, `scripts/enrich_async`) requires the Go API to be stopped before it can connect. Acceptable for local dev and pre-launch. **Three options previously evaluated for production**:
   - (a) Keep DuckDB as the read store, move the write path (`event`, `contribution_log`, `contributor`) to Postgres. Sync DuckDB nightly via `cmd/refresh-popularity` (#10i). Cleanest separation; matches existing architecture intent.
   - (b) Run a single long-lived Go process that owns the DB file and exposes a write API; bulk Python pipelines hit that API instead of the file directly. Adds a coordination layer but stays single-store.
   - (c) Periodic write windows: schedule batch jobs to run during low-traffic windows; the API briefly drains and yields the lock. Simplest, but introduces visible downtime windows.

   **2026-05-10 launch decision: path β (defer)** — single Fly VM keeps the
   DuckDB lock as the only writer in production for now (no Python batch runs
   against the live volume; enrichment continues against a local DuckDB on
   MacBook, then the file is shipped via deploy or `fly ssh sftp` upload). This
   is acceptable while traffic is low and enrichment is operator-driven.
   **Trigger to revisit**: when (i) bulk enrichment becomes daily-or-faster,
   (ii) horizontal scale is required, or (iii) community-contribution writes
   land — pick option (a) and migrate.

---

## 17. Engagement analytics (F8) — day-1 design

Track user behavior from launch so we can:
- prioritize which persons get enriched next (whose biographies users actually open),
- surface trending people on landing,
- power future investor / community-facing analytics,
- avoid retrofitting tracking after the fact (loses 3-6 months of signal).

### 17.1 Event taxonomy

| `event_type` | Trigger | `person_id` | `query` | Notes |
|---|---|---|---|---|
| `page_view` | `/p/[id]` mount | yes | — | one per route navigation, not per re-render |
| `search` | SearchBox debounced query fires `/api/search` | optional (top result) | yes | only logged on result-returning query, not while typing |
| `modal_open` | PersonModal first render in viewport | yes | — | strong intent signal |
| `tree_expand` | Click node → re-render tree centered on it | yes | — | discovery signal |
| `node_click` | Click on non-ego node within current tree | yes | — | hover-then-click (lower intent than expand) |
| `external_click` | Click Wikipedia / Wikidata source link in modal | yes | — | exit signal, still counts as engagement |

All events POSTed to `POST /api/event`. Client-side fire-and-forget via `navigator.sendBeacon` so navigation isn't blocked.

### 17.2 Scoring algorithm

`person_popularity.score` is a weighted composite, rebuilt nightly by `cmd/refresh-popularity`:

```
score = views_30d
      + 2 * modal_opens_30d
      + 3 * tree_expands_30d
      + 5 * external_clicks_30d
      + recency_boost
```

`recency_boost = log10(1 + events_last_24h) * 10` — keeps the table responsive to news cycles without being dominated by 24h spikes.

Why these weights:
- view = 1 (cheap, includes bots, drive-by)
- modal_open = 2 (user paused to read bio)
- tree_expand = 3 (user navigated *to* this person from another — strongest interest signal)
- external_click = 5 (rare, indicates serious research intent)

Tunable in `cmd/refresh-popularity/main.go` constants; not yet a config file (premature).

### 17.3 Backend endpoints

- `POST /api/event` — body: `{ event_type, person_id?, query?, session_id, referrer? }`. Validates `session_id` is uuid format. Rate limit: 100 events/min per `session_id` (token bucket in memory; OK for single-instance, swap to Redis if horizontal scale). Returns `204`.
- `GET /api/admin/popularity?limit=100&missing_bio=true` — gated by `Authorization: Bearer $ADMIN_TOKEN`. Returns priority enrichment queue:
  ```
  [{ qid, birth_name, wikipedia_vi_title, score, views_30d, last_event_at }]
  ```
- `GET /api/trending?window=7d&limit=10` — public. Used on landing page "Đang được tìm nhiều" section. Cached 5 min.

### 17.4 Frontend instrumentation

`lib/track.ts`:

```ts
// session_id from localStorage; generated once per device
const sessionId = getOrCreateSessionId()

// batched 500ms window to coalesce burst events
const queue: EventPayload[] = []
let timer: number | null = null

export function track(type: EventType, payload?: Partial<EventPayload>) {
  queue.push({ event_type: type, session_id: sessionId, ...payload })
  if (!timer) timer = window.setTimeout(flush, 500)
}

function flush() {
  const batch = queue.splice(0)
  navigator.sendBeacon('/api/event', JSON.stringify({ events: batch }))
  timer = null
}
```

Instrumentation points (4 call sites):
- `app/p/[id]/page.tsx` — `track('page_view', { person_id })` on mount.
- `components/search-box.tsx` — `track('search', { query, person_id: topResult?.id })` after debounce + result.
- `components/person-modal.tsx` — `track('modal_open', { person_id })` on mount.
- `components/family-tree.tsx` — `track('tree_expand', { person_id })` on node click that triggers re-center.

### 17.5 Privacy

- **No PII**: never log email, name, IP. `session_id` is a random UUID generated client-side, not derivable from user identity.
- **IP not stored**: `country` derived from `CF-IPCountry` header and stored as 2-char code only.
- **UA hash, not UA**: `sha1(user_agent)` stored; original UA discarded at insert time.
- **Retention**: 90 days raw events. After that, aggregated into `person_popularity` and source events hard-deleted.
- **User control**: localStorage flag `wikipath:no-track=1` (set via footer link "Không theo dõi tôi") makes `track()` a no-op. Documented in `/about` and `PRIVACY.md`.
- **No cross-site tracking**: `session_id` scoped to wikipath origin only.
- **GDPR/Vietnamese PDPL stance**: lawful basis = legitimate interest (product analytics, no profiling, no ads, no third-party sharing).

### 17.6 Priority enrichment use case

After 30 days of traffic, the enrichment runner switches from SPARQL fame proxy (has-image) to popularity-driven queue:

```sql
SELECT p.id, p.wikidata_qid, p.birth_name, pop.score
FROM person p
JOIN person_popularity pop ON p.id = pop.person_id
WHERE (p.bio_short IS NULL OR p.bio_short = '')
  AND p.wikipedia_vi_url IS NOT NULL
ORDER BY pop.score DESC
LIMIT 200;
```

→ feeds `enrich_async.py` as input list. Closes the feedback loop: users click X, X gets enriched first, X's tree gets richer, more users find X.

Cold start: until 30 days of traffic exist, fallback to SPARQL fame proxy. Hybrid query (popularity OR fame) for the first quarter.

### 17.7 Out of scope for analytics v0.1

- A/B testing framework (premature)
- User-level dashboards (no login yet)
- Funnel reports (no conversion funnels yet)
- Per-day time series UI (raw events queryable via SQL is enough for now)
- Third-party analytics SDKs of any kind — keep self-hosted, no external pixel

---

## Notes on the v0 archive

The original wikipath was a clean-room reimplementation of the
"Six Degrees of Wikipedia" pattern (celebrity-hop BFS over a Wikipedia
mention graph). The v0 SPEC and sprint plan are preserved in
`docs/SPEC-v0-celebrity-hops.md` and `docs/SPRINT-PLAN-v0.md` for
historical context. The v0 Go source code (`cmd/crawl`, `cmd/serve`,
`internal/crawl`, `internal/server`, `internal/wiki`, `internal/graph`,
`seeds.txt`, `graph.json`) was removed when the project pivoted to v1.

v1 was written fresh against this SPEC and shares no source with v0.
The pivot rationale: the celebrity-hop problem had stronger existing
implementations, and no comparable open-data tool existed for
Vietnamese family relationships.

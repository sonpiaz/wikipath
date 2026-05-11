# Data Sources

wikipath's database is compiled from multiple upstream sources, each
with its own license and reliability profile. This page tells you what
came from where, how we record provenance, and how you can verify a
given fact.

## Primary sources

### 1. Wikidata

- **URL**: https://www.wikidata.org
- **License**: CC0 (public domain dedication)
- **What we use**: Structured claims — P31 (instance-of), P27
  (citizenship), P569 (date of birth), P570 (date of death), P19 (place
  of birth), P22 (father), P25 (mother), P26 (spouse), P40 (child), P3373
  (sibling), P172 (ethnicity), P18 (image), P106 (occupation).
- **Coverage**: ~5,600 Vietnamese persons in wikipath as of 2026-05-10.
- **In the DB**: `person.wikidata_qid` = the source QID;
  `person.primary_source = 'wikidata'` when this was the original
  insert; `relation.source_kind = 'wikidata'`.
- **Recommended verification**: `https://www.wikidata.org/wiki/<QID>`.

### 2. Wikipedia VN (vi.wikipedia.org)

- **URL**: https://vi.wikipedia.org
- **License**: CC BY-SA 3.0 / 4.0 (article text). Facts are not
  copyrightable; structured extraction is fair use.
- **What we use**: Infobox templates (`{{Thông tin nhân vật}}`,
  `{{Thông tin vua}}`, etc.) for father, mother, spouse, child,
  sibling, birth/death dates and places, dynasty, lineage; full article
  text as the input for LLM-based bio extraction.
- **In the DB**: `person.wikipedia_vi_url` points to the source article;
  `relation.source_kind = 'wikipedia_vi'` or `'llm_enrich'` (when the
  fact came via LLM extraction with source-sentence validation).

### 3. LLM enrichment via the [Kyma API](https://api.kymaapi.com) gateway

- **What it is**: A pipeline that feeds a Wikipedia VN article excerpt
  to an LLM and asks for structured extraction (bio, dates, family).
- **Why Kyma**: Asia-region latency, OpenAI-compatible endpoint, and a
  multilingual model catalog that includes Vietnamese-strong models.
  Swap models via the `LLM_MODEL` constant in
  `scripts/enrich_async.py` without code changes.
- **Production default**: `deepseek-v4-pro` (preview tier). Achieved
  99.5% extraction success on a 200-profile pilot, with average
  confidence 89.8/100 after the source-sentence validation.
- **Stable alternative**: `deepseek-v3`. We benchmarked it independently
  on 3 Wikipedia VN articles via `scripts/bench_models.py` and observed
  100% success, 14.3s median latency, and 100% source-sentence
  substring-match rate. Drop-in replacement when the preview tier is
  unavailable.
- **Other Kyma models tested**: `gemini-2.5-flash`, `glm-4.5-air`,
  `qwen-3.6-plus`. None of these reached the success threshold for
  this specific extraction task in our bench (timeouts on long
  articles, or invalid-JSON responses). They are useful for other
  workloads but not currently recommended for VN-language structured
  extraction without further prompt tuning.
- **Hallucination guard**: Every extracted fact must include a
  `source_sentence` field that is a **literal substring** of the input
  article. We re-verify the substring match server-side and lower the
  confidence score if the match is partial.
- **Confidence tiers**: 90 (substring match), 70 (partial match on
  first + last 4 tokens), 50 (no substring match — flagged for review),
  40 (no source_sentence — rejected for auto-publish).
- **Schema-level guard**: Names that fail `is_valid_person_name()` are
  rejected at insert time. See SPEC §4.8 for the filter.
- **In the DB**: `relation.source_kind = 'llm_enrich'`, with the
  source_sentence preserved in `relation.source_ref`.

### 4. Hand-curated seed (`data/seed-vi.yml`)

- **What it is**: 49 hand-edited profiles representing the major
  dynasties (Lý, Trần, Lê, Tây Sơn, Nguyễn) and key modern figures,
  used to bootstrap the schema during development.
- **In the DB**: `relation.source_kind = 'community'` with source_ref
  pointing to `seed-vi.yml`.

### 5. Wikimedia Commons (P18 images)

- **URL**: https://commons.wikimedia.org
- **License**: Per-file; mostly CC BY-SA 4.0 or PD.
- **What we use**: The P18 image filename from Wikidata is converted
  into a Special:FilePath URL. We do NOT cache or rehost the image
  itself.
- **In the DB**: `person.avatar_url` points directly to the Commons URL.
- **Attribution**: Each PersonModal shows source badges (Wikidata
  + Wikipedia) which link to the upstream page where the image's
  individual license is documented.

## Future sources (not yet integrated)

- **Hand-curated books**: Lineage histories ("Nguyễn Phúc tộc thế phả",
  "Đại Việt sử ký toàn thư"). High-trust source, requires manual
  citation per record.
- **Oral histories**: Family interviews with attribution. Lower trust
  default, requires `consent_status` for living references.
- **News archives**: VNExpress, Tuoi Tre, Thanh Nien for modern figures.
  Cited inline per claim.

## Source-trust scoring

Each `relation` row stores a `confidence` score 0–100. The DB
`person.trust_score` is a running aggregate:

- 95+: All facts from Wikidata + Wikipedia VN with corroborating sources.
- 80–94: Mostly Wikidata or Wikipedia, plus LLM enrichment for bio.
- 60–79: Single source, no cross-validation. UI shows a "limited
  source" badge.
- <60: Disputed or unverified. Hidden from public read unless
  `consent_status` overrides. Flagged for moderation queue.

## How to dispute a source

See [TAKEDOWN.md](TAKEDOWN.md). Disputed records are not erased — they
gain additional `relation` rows with alternate `source_kind` and lower
`confidence` until consensus emerges.

## Last updated

2026-05-10.

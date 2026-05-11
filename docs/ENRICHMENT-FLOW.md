# wikipath enrichment flow

Operational playbook for bio_short enrichment via Kyma LLM. Designed for runs
from 50 rows up to 100k+. Read this top-to-bottom before kicking off a new
campaign; sections build on each other.

---

## 0. Principles

1. **Spend audit money before LLM money.** A 30-second SQL scan stops more
   waste than any post-hoc cleanup.
2. **Doubling, not Big Bang.** Run 50, then 100, then 200 … audit each gate.
   If false-positive rate creeps past 2%, halt and fix before scaling.
3. **Garbage in is garbage paid for.** Filter the candidate pool to skip
   isolated nodes, missing sources, and pollution before paying per-row.
4. **Bio is precision-biased.** The pipeline rejects "low_conf" output. Treat
   a low pass-rate as a signal that the source article is thin, not that we
   should loosen validators.
5. **Cross-source disagreement is a separate problem.** Bio is from Wikipedia
   VN; DB years often came from Wikidata. When they disagree, neither is
   automatically wrong — log it and surface, do not silently overwrite.

---

## 1. Pre-flight gate (always)

```bash
python scripts/quality_scan.py --limit 5
```

Read `data/quality_report.md`. Halt if ANY of these are above zero and
unexplained:

| Check                       | Action if non-zero |
|-----------------------------|--------------------|
| `garbage_names`             | Run cleanup SQL (drops Q-only / year-only / len<2). |
| `era_birth_mismatch`        | Run cleanup SQL (re-buckets era from birth_date_y). |
| `future_dates`              | Investigate — never normal. |
| `self_relations`            | Investigate — should be impossible. |
| `nameless_no_source`        | Should not enrich these. Drop or wait for backfill. |
| `parent_child_age_gap`      | Don't block; community can correct via GitHub. |
| `likely_dead_no_death_year` | Don't block; backfill via Wikipedia title is separate task. |
| `duplicate_pairs`           | Don't block enrichment, but track for manual merge later. |
| `isolated_nodes`            | Don't enrich them — they waste credit. Filter at candidate pick. |

Run the targeted cleanup SQL when needed:

```bash
duckdb wikipath.duckdb -c ".read scripts/cleanup_quality_issues.sql"
python scripts/quality_scan.py --limit 1   # confirm counts dropped
```

---

## 2. Pick candidates

Two pickers, two pools.

### Local DB pool — for sanity pilots (≤30 rows)

```bash
python scripts/pick_db_candidates.py --limit 50 -o data/candidates_pilot.json
```

Picks from `person` table where:
- `wikipedia_vi_url IS NOT NULL` (LLM has ground truth)
- `bio_short` is empty
- name passes display validators
- has ≥1 relation (skip isolated, override with `--allow-isolated`)

The local pool is small (~30 rows post-cleanup) because most imports never
wrote a Wikipedia URL. Use for pipeline smoke tests.

### SPARQL pool — for real campaigns

```bash
python scripts/pick_candidates.py --limit 100 -o data/candidates_batch_100.json
```

Pulls from Wikidata SPARQL: human + (VN citizenship OR VN ethnicity) +
vi.wikipedia sitelink + birth in `[year_from, year_to]` (default 1200-2010).
Ranks by sitelink count then has-image then birth_date. Automatically skips
QIDs already enriched in the local DB.

Pool size today: ~4,700 candidates that match the SPARQL filter. Subtract
already-enriched and you have today's headroom.

Tip: use `--skip-first` to chain non-overlapping batches if you want to keep
the same global ranking across runs.

---

## 3. Run enrichment

```bash
KYMA_API_KEY=$(grep '^KYMA_API_KEY=' ~/kyma-api/.env | cut -d= -f2) \
  python scripts/enrich_async.py \
    --candidates data/candidates_batch_NNN.json \
    --concurrency 8 \
    --checkpoint-every 20
```

- `--concurrency 8` is the sweet spot on Kyma + vi.wikipedia rate limits.
- `--checkpoint-every 20` writes + DuckDB CHECKPOINT every 20 successes. Set
  it lower for short batches, higher for very large ones.
- Default model is `deepseek-v3`. Override with `LLM_MODEL=...` env if you
  benchmark a new model — keep the previous one in the audit baseline so you
  can compare regression.

Expected throughput: 2-5 s/profile end-to-end (Wikipedia fetch + LLM + DB
write). 100 rows in ~8 minutes is normal.

Watch the per-row line. `low_conf flagged` = pipeline rejected an LLM output
as too thin; `name-rejected` = relations referenced a name that failed the
display validators. These are good — they prove the validators are firing.

---

## 4. Audit gate (after every batch)

Pull a random sample at least 1.5× larger than the false-positive budget. For
a 2% gate that means ≥10 rows for a batch of 50, ≥20 rows for 200+.

```bash
duckdb wikipath.duckdb -c "
SELECT birth_name, birth_date_y AS db_birth, death_date_y AS db_death,
       substring(bio_short, 1, 220) AS bio
FROM person
WHERE wikidata_qid IN (SELECT qid FROM read_json('data/candidates_batch_NNN.json'))
  AND bio_short IS NOT NULL
ORDER BY random() LIMIT 15"
```

For each row check:

1. **Language**: must be Vietnamese.
2. **Fabrication**: every concrete claim (role, date, place) must be
   verifiable in the Wikipedia VN article. Especially watch invented
   institutions, fake titles, made-up family ties.
3. **Year alignment**: if the bio quotes a birth/death year, it should match
   `db_birth` / `db_death`. Cross-source mismatch is its own bucket — see §5.
4. **Length**: 1-2 sentences, ~120-200 chars. Reject if 3+ sentences, or if
   it reads like a Wikipedia full intro (bloated).

If false-positive rate ≥ 2%, HALT. Investigate the failing rows. Common
causes:
- Wikipedia article is a disambiguation page or a stub.
- LLM concatenated two persons sharing a name.
- Wikidata QID points to a different person than the linked Wikipedia
  article (rare but happens).

---

## 5. Cross-source year mismatch (separate stream)

Not an enrichment defect, but a real user-visible inconsistency. Pattern:
DB year says X (from Wikidata import), bio quotes Y (from Wikipedia VN).
The header will show X while the bio quotes Y; users will spot it.

Observed rate on the 100-row batch (2026-05-10): **3/22 = 13.6%** for
pre-1950 political/intellectual figures. The Wikipedia VN year is usually
right when the two disagree, but not always.

Two policies; the project has not chosen one yet:

- **(A) Wikipedia wins**: post-enrichment script re-extracts year from bio,
  updates `birth_date_y` / `death_date_y` if different. Cheap to add, but
  reduces ground truth on the database side.
- **(B) Surface both**: keep DB year, render `(theo Wikipedia: 1908)` next to
  it when bio mentions a different year. More honest, more UI work.

Pick a policy before scaling past a few hundred rows or this will compound.

---

## 6. Doubling protocol — concrete sequence

```
pilot     pick_db_candidates  --limit 30    →  audit 8 rows
batch_50  pick_candidates     --limit 50    →  audit 10 rows
batch_100 pick_candidates     --limit 100   →  audit 15 rows
batch_200 pick_candidates     --limit 200   →  audit 20 rows
batch_400 pick_candidates     --limit 400   →  audit 25 rows
batch_800 pick_candidates     --limit 800   →  audit 25 rows
…doubles until pool exhausted
```

Rules:
- Audit **before** kicking off the next batch.
- If audit fails: halt, investigate, fix the cause, then re-run *the same
  batch size* (not the next one). Doubling rewards stability, not speed.
- If consecutive audits all 0/N: confidence rises. After 3 clean audits at
  ≥100 rows you can stop sampling 25 each time and drop to 15.

Cost projection (deepseek-v3 ~ $0.003/row):

| Batch | Marginal cost | Cumulative |
|-------|---------------|------------|
| 50    | $0.15         | $0.15      |
| 100   | $0.30         | $0.45      |
| 200   | $0.60         | $1.05      |
| 400   | $1.20         | $2.25      |
| 800   | $2.40         | $4.65      |
| 1600  | $4.80         | $9.45      |
| 3200  | $9.60         | $19.05     |

Pool ceiling today is ~4,400 unenriched candidates with Wikipedia URLs;
covering the pool fully costs ~$15 if every batch passes audit.

---

## 7. Scaling to 100k+ rows

The current pool ceiling is the SPARQL filter (P31=human + VN
citizenship/ethnicity + vi.wikipedia sitelink). To go beyond, options:

1. **Backfill Wikipedia URL for existing DB rows**. Many `person` records
   have `wikidata_qid` but no `wikipedia_vi_url` because the original
   importer did not query `wikipedia_sitelink`. A one-off SPARQL pass
   binds vi-wiki titles → backfill URLs. Adds thousands of rows to the
   eligible pool without new SPARQL imports.
2. **Relax language**: pull `en.wikipedia` as fallback ground truth. LLM
   would have to translate. Risk: bio voice drifts from VN style.
3. **Multi-language import for VN diaspora**. Some VN-American /
   VN-French figures only have `fr.wikipedia` or `en.wikipedia` articles.
4. **Translate vi.wikipedia full bio into bio_full**, with bio_short as a
   model-summarized truncation. Doubles the LLM token cost but unlocks the
   `bio_full` field which is currently always NULL.

Operational guardrails for 100k+ runs:
- Run inside a tmux session on the Mac mini; the MacBook will sleep.
- Capture stdout to a timestamped log file so you can replay failures.
- Schedule a separate Fly process to upload the DB to the live volume at
  the end (single-writer lock — pause the API briefly during swap).
- Bring forward the cross-source year reconciliation policy from §5 first;
  letting 100k rows accumulate this defect is much worse than fixing the
  policy now.
- Track `Kyma credit burn` in a dashboard — easy to over-spend a $50 limit
  on a careless `--limit 50000`.

---

## 8. File map

| File                                       | Role                                       |
|--------------------------------------------|--------------------------------------------|
| `scripts/quality_scan.py`                  | Pre-flight DB audit; emits json+md.        |
| `scripts/cleanup_quality_issues.sql`       | Idempotent fix for garbage + era buckets.  |
| `scripts/pick_db_candidates.py`            | Pick from local DB (small pilots).         |
| `scripts/pick_candidates.py`               | Pick from Wikidata SPARQL (bulk).          |
| `scripts/enrich_async.py`                  | Concurrent LLM enrichment + DB writes.     |
| `data/quality_report.{json,md}`            | Output of quality_scan.                    |
| `data/candidates_*.json`                   | Per-batch candidate lists (gitignored OK). |
| `docs/ENRICHMENT-FLOW.md`                  | This document.                             |
